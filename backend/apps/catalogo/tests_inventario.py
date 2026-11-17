"""Stock mínimo, vencimientos, costos ocultos y kardex. Ejecutar: python manage.py test apps.catalogo"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.usuarios.models import UserProfile

from .models import Categoria, MovimientoInventario, Producto, Proveedor

User = get_user_model()


class InventarioTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.admin, rol=UserProfile.Rol.ADMINISTRADOR)
        self.cajero = User.objects.create_user("cajero_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.cajero, rol=UserProfile.Rol.CAJERO)
        hoy = timezone.localdate()
        cat = Categoria.objects.create(nombre="Varios")
        crear = lambda **d: Producto.objects.create(categoria=cat, precio=1000, costo=500, **d)  # noqa: E731
        self.cuaderno = crear(nombre="Cuaderno", seguimiento_inventario=True, stock=10, stock_minimo=5)
        self.lapiz = crear(nombre="Lápiz", seguimiento_inventario=True, stock=3, stock_minimo=5)
        self.borrador = crear(nombre="Borrador", seguimiento_inventario=True, stock=0)
        self.dulce = crear(
            nombre="Chocolatina", seguimiento_inventario=True, stock=20, fecha_vencimiento=hoy + timedelta(days=10)
        )
        self.vencido = crear(
            nombre="Gomitas", seguimiento_inventario=True, stock=8, fecha_vencimiento=hoy - timedelta(days=1)
        )
        self.servicio = crear(nombre="Fotocopia", seguimiento_inventario=False)
        self.proveedor = Proveedor.objects.create(nombre="Distribuidora")

    def productos(self, usuario):
        self.client.force_authenticate(usuario)
        return {p["nombre"]: p for p in self.client.get("/api/productos/").data}

    def test_estado_de_stock_y_vencimiento_en_el_json(self):
        p = self.productos(self.admin)
        self.assertEqual(p["Cuaderno"]["estadoStock"], "ok")
        self.assertEqual(p["Lápiz"]["estadoStock"], "bajo")
        self.assertEqual(p["Borrador"]["estadoStock"], "agotado")
        self.assertIsNone(p["Fotocopia"]["estadoStock"])
        self.assertEqual(p["Chocolatina"]["alertaVencimiento"], "proximo")
        self.assertEqual(p["Chocolatina"]["diasParaVencer"], 10)
        self.assertEqual(p["Gomitas"]["alertaVencimiento"], "vencido")
        self.assertIsNone(p["Cuaderno"]["alertaVencimiento"])
        self.assertEqual(p["Cuaderno"]["stockMinimo"], 5)

    def test_solo_el_administrador_ve_costos(self):
        self.assertNotIn("costo", self.productos(self.cajero)["Cuaderno"])
        self.assertEqual(self.productos(self.admin)["Cuaderno"]["costo"], 500)

    def test_endpoint_de_alertas(self):
        self.client.force_authenticate(self.cajero)
        datos = self.client.get("/api/productos/alertas/").data
        nombres = lambda clave: [p["nombre"] for p in datos[clave]]  # noqa: E731
        self.assertEqual(nombres("agotados"), ["Borrador"])
        self.assertEqual(nombres("stockBajo"), ["Lápiz"])
        self.assertEqual(nombres("porVencer"), ["Chocolatina"])
        self.assertEqual(nombres("vencidos"), ["Gomitas"])

    def test_ajuste_manual_queda_en_el_kardex(self):
        self.client.force_authenticate(self.admin)
        url = f"/api/productos/{self.cuaderno.id}/ajustar-stock/"
        respuesta = self.client.post(url, {"stock": 7, "motivo": "Conteo físico"}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.assertEqual(respuesta.data["stock"], 7)
        movimiento = MovimientoInventario.objects.get(producto=self.cuaderno)
        self.assertEqual(movimiento.tipo, "AJUSTE")
        self.assertEqual(movimiento.cantidad, -3)
        self.assertEqual(movimiento.stock_resultante, 7)
        self.assertEqual(movimiento.nota, "Conteo físico")
        self.assertEqual(movimiento.usuario, self.admin)

    def test_reglas_del_ajuste_manual(self):
        url = f"/api/productos/{self.cuaderno.id}/ajustar-stock/"
        self.client.force_authenticate(self.cajero)
        self.assertEqual(self.client.post(url, {"stock": 1, "motivo": "x"}, format="json").status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(url, {"stock": 1, "motivo": " "}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"stock": 10, "motivo": "igual"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"stock": -1, "motivo": "x"}, format="json").status_code, 400)
        servicio = f"/api/productos/{self.servicio.id}/ajustar-stock/"
        self.assertEqual(self.client.post(servicio, {"stock": 5, "motivo": "x"}, format="json").status_code, 400)

    def test_kardex_registra_compra_venta_y_reembolso(self):
        self.client.force_authenticate(self.admin)
        compra = self.client.post(
            "/api/compras/",
            {"proveedorId": self.proveedor.id, "items": [{"productoId": self.cuaderno.id, "cantidad": 5, "costo": 500}]},
            format="json",
        ).data
        venta = self.client.post(
            "/api/ventas/",
            {"items": [{"productoId": self.cuaderno.id, "cantidad": 2}], "metodoPago": "Nequi", "cerrar": True},
            format="json",
        ).data
        self.client.post(
            f"/api/ventas/{venta['id']}/reembolsos/",
            {"items": [{"productoId": self.cuaderno.id, "cantidad": 1}]},
            format="json",
        )
        self.client.force_authenticate(self.cajero)  # el cajero también puede consultar el kardex
        kardex = self.client.get(f"/api/productos/{self.cuaderno.id}/kardex/").data
        movimientos = kardex["movimientos"]
        self.assertEqual([m["tipo"] for m in movimientos], ["REEMBOLSO", "VENTA", "COMPRA"])
        self.assertEqual([m["cantidad"] for m in movimientos], [1, -2, 5])
        self.assertEqual(movimientos[0]["stockResultante"], 14)
        self.assertEqual(movimientos[1]["referencia"], venta["numero"])
        self.assertEqual(movimientos[2]["referencia"], compra["numero"])
        self.assertEqual(movimientos[2]["usuario"], "admin_test")
        self.assertNotIn("costo", kardex["producto"])

    def test_editar_stock_en_el_formulario_crea_ajuste(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(f"/api/productos/{self.cuaderno.id}/", {"stock": 12}, format="json")
        movimiento = MovimientoInventario.objects.get(producto=self.cuaderno)
        self.assertEqual((movimiento.tipo, movimiento.cantidad), ("AJUSTE", 2))

    def test_crear_producto_con_stock_registra_saldo_inicial(self):
        self.client.force_authenticate(self.admin)
        creado = self.client.post(
            "/api/productos/",
            {"nombre": "Regla", "categoriaId": self.cuaderno.categoria_id, "precio": 2000,
             "seguimientoInventario": True, "stock": 9, "stockMinimo": 3,
             "fechaVencimiento": None},
            format="json",
        ).data
        movimiento = MovimientoInventario.objects.get(producto_id=creado["id"])
        self.assertEqual((movimiento.tipo, movimiento.cantidad), ("INICIAL", 9))
        self.assertEqual(creado["stockMinimo"], 3)
