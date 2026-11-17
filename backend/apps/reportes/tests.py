"""Pruebas de reportes. Ejecutar: python manage.py test apps.reportes"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalogo.models import Categoria, Descuento, Producto, Proveedor
from apps.usuarios.models import UserProfile
from apps.ventas.models import Venta

User = get_user_model()


class ReportesTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.admin, rol=UserProfile.Rol.ADMINISTRADOR)
        self.cajero = User.objects.create_user("cajero_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.cajero, rol=UserProfile.Rol.CAJERO)
        categoria = Categoria.objects.create(nombre="Papelería")
        self.cuaderno = Producto.objects.create(
            nombre="Cuaderno", categoria=categoria, precio=10000, seguimiento_inventario=True, stock=50
        )
        self.lapiz = Producto.objects.create(
            nombre="Lápiz", categoria=categoria, precio=2000, seguimiento_inventario=True, stock=50
        )
        self.proveedor = Proveedor.objects.create(nombre="Distribuidora Andina")
        self.diez = Descuento.objects.create(nombre="Diez", tipo="PORCENTAJE", valor=10)

        self.hoy = timezone.localdate()
        self.ayer = self.hoy - timedelta(days=1)

        # Ventas de hoy (como cajero)
        self.client.force_authenticate(self.cajero)
        self.v1 = self.vender([(self.cuaderno, 2), (self.lapiz, 1)], "Efectivo", valorRecibido=22000)
        self.v2 = self.vender([(self.lapiz, 5)], "Nequi", descuentoId=self.diez.id)  # 10.000 - 1.000
        self.client.post(  # venta abierta: no cuenta
            "/api/ventas/", {"items": [{"productoId": self.cuaderno.id, "cantidad": 9}]}, format="json"
        )
        # Venta de ayer
        self.v3 = self.vender([(self.cuaderno, 1)], "Nequi")
        Venta.objects.filter(pk=self.v3["id"]).update(
            fecha=timezone.now() - timedelta(days=1)
        )
        self.client.force_authenticate(self.admin)

    def vender(self, lineas, metodo, **extra):
        datos = {
            "items": [{"productoId": p.id, "cantidad": c} for p, c in lineas],
            "metodoPago": metodo,
            "cerrar": True,
            **extra,
        }
        respuesta = self.client.post("/api/ventas/", datos, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        return respuesta.data

    def test_reportes_solo_para_administrador(self):
        self.client.force_authenticate(self.cajero)
        for ruta in ("ventas", "productos-mas-vendidos", "compras", "faltantes-frecuentes"):
            with self.subTest(ruta=ruta):
                respuesta = self.client.get(f"/api/reportes/{ruta}/")
                self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_ventas_totales_de_hoy(self):
        datos = self.client.get("/api/reportes/ventas/").data  # por defecto: hoy
        self.assertEqual(datos["cantidadVentas"], 2)
        self.assertEqual(datos["subtotal"], 32000)
        self.assertEqual(datos["descuentos"], 1000)
        self.assertEqual(datos["totalVendido"], 31000)
        self.assertEqual(datos["ticketPromedio"], 15500)
        metodos = {fila["metodoPago"]: fila["total"] for fila in datos["porMetodoPago"]}
        self.assertEqual(metodos, {"Efectivo": 22000, "Nequi": 9000})

    def test_ventas_por_rango_incluye_ayer(self):
        url = f"/api/reportes/ventas/?desde={self.ayer.isoformat()}&hasta={self.hoy.isoformat()}"
        datos = self.client.get(url).data
        self.assertEqual(datos["cantidadVentas"], 3)
        self.assertEqual(datos["totalVendido"], 41000)
        self.assertEqual(len(datos["porDia"]), 2)
        solo_ayer = self.client.get(f"/api/reportes/ventas/?desde={self.ayer}&hasta={self.ayer}").data
        self.assertEqual(solo_ayer["cantidadVentas"], 1)

    def test_reembolsos_restan_en_total_neto(self):
        self.client.post(
            f"/api/ventas/{self.v1['id']}/reembolsos/",
            {"items": [{"productoId": self.lapiz.id, "cantidad": 1}]},
            format="json",
        )
        datos = self.client.get("/api/reportes/ventas/").data
        self.assertEqual(datos["totalReembolsado"], 2000)
        self.assertEqual(datos["totalNeto"], 29000)

    def test_productos_mas_vendidos(self):
        url = f"/api/reportes/productos-mas-vendidos/?desde={self.ayer}&hasta={self.hoy}"
        productos = self.client.get(url).data["productos"]
        self.assertEqual(productos[0]["nombre"], "Lápiz")
        self.assertEqual(productos[0]["unidadesVendidas"], 6)
        self.assertEqual(productos[1]["nombre"], "Cuaderno")
        self.assertEqual(productos[1]["unidadesVendidas"], 3)
        self.assertEqual(productos[1]["ventas"], 2)
        limitado = self.client.get(url + "&limite=1").data["productos"]
        self.assertEqual(len(limitado), 1)

    def test_compras_por_rango(self):
        self.client.post(
            "/api/compras/",
            {
                "proveedorId": self.proveedor.id,
                "items": [{"productoId": self.cuaderno.id, "cantidad": 10, "costo": 6000}],
            },
            format="json",
        )
        datos = self.client.get("/api/reportes/compras/").data
        self.assertEqual(datos["cantidadCompras"], 1)
        self.assertEqual(datos["totalComprado"], 60000)
        self.assertEqual(datos["porProveedor"][0]["proveedorNombre"], "Distribuidora Andina")

    def test_faltantes_frecuentes(self):
        for nombre in ("Témperas", "tempera", "Escarcha"):
            self.client.post("/api/faltantes/", {"nombre": nombre, "tipo": "inexistente"}, format="json")
        datos = self.client.get("/api/reportes/faltantes-frecuentes/").data
        self.assertEqual(datos["faltantes"][0]["nombreNormalizado"], "tempera")
        self.assertEqual(datos["faltantes"][0]["solicitudes"], 2)
        self.assertEqual(datos["faltantes"][0]["posicion"], 1)

    def test_parametros_invalidos(self):
        self.assertEqual(self.client.get("/api/reportes/ventas/?desde=16-11-2026").status_code, 400)
        url = f"/api/reportes/ventas/?desde={self.hoy}&hasta={self.ayer}"
        self.assertEqual(self.client.get(url).status_code, 400)
        url = "/api/reportes/productos-mas-vendidos/?limite=0"
        self.assertEqual(self.client.get(url).status_code, 400)
