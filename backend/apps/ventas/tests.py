"""
Pruebas de ventas, corrección y reembolsos. Ejecutar: python manage.py test apps.ventas

Datos base: Cuaderno $10.000 (stock 10), Lápiz $2.000 (stock 5), Impresión $500 (sin inventario).
Los precios ya incluyen IVA.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalogo.models import Categoria, Cliente, Descuento, Producto
from apps.usuarios.models import UserProfile

from .models import Venta

User = get_user_model()


class BaseVentasTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.admin, rol=UserProfile.Rol.ADMINISTRADOR)
        self.cajero = User.objects.create_user("cajero_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.cajero, rol=UserProfile.Rol.CAJERO)

        categoria = Categoria.objects.create(nombre="Papelería")
        self.cuaderno = Producto.objects.create(
            nombre="Cuaderno", categoria=categoria, precio=10000, costo=6000,
            seguimiento_inventario=True, stock=10,
        )
        self.lapiz = Producto.objects.create(
            nombre="Lápiz", categoria=categoria, precio=2000, costo=800,
            seguimiento_inventario=True, stock=5,
        )
        self.impresion = Producto.objects.create(
            nombre="Impresión", categoria=categoria, precio=500, seguimiento_inventario=False,
        )
        self.cliente = Cliente.objects.create(nombre="Ana")
        self.client.force_authenticate(self.cajero)

    # --- utilidades ---
    def items(self, cuadernos=2, lapices=1):
        lineas = []
        if cuadernos:
            lineas.append({"productoId": self.cuaderno.id, "cantidad": cuadernos})
        if lapices:
            lineas.append({"productoId": self.lapiz.id, "cantidad": lapices})
        return lineas

    def crear(self, **datos):
        datos.setdefault("items", self.items())
        return self.client.post("/api/ventas/", datos, format="json")

    def crear_cerrada(self, **datos):
        datos.setdefault("metodoPago", "Nequi")
        respuesta = self.crear(cerrar=True, **datos)
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        return respuesta.data

    def stock(self, producto):
        producto.refresh_from_db()
        return producto.stock


class VentasAbiertasYCierreTests(BaseVentasTest):
    def test_guardar_venta_abierta_no_descuenta_stock(self):
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["estado"], "abierta")
        self.assertEqual(respuesta.data["total"], 22000)
        self.assertEqual(len(respuesta.data["items"]), 2)
        self.assertEqual(self.stock(self.cuaderno), 10)

    def test_venta_sin_items_es_rechazada(self):
        respuesta = self.client.post("/api/ventas/", {"items": []}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        respuesta = self.client.post("/api/ventas/", {}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retomar_editar_y_cerrar_en_efectivo(self):
        venta = self.crear().data
        editar = self.client.patch(
            f"/api/ventas/{venta['id']}/", {"items": self.items(cuadernos=1, lapices=2)}, format="json"
        )
        self.assertEqual(editar.status_code, status.HTTP_200_OK, editar.data)
        self.assertEqual(editar.data["total"], 14000)

        cerrar = self.client.post(
            f"/api/ventas/{venta['id']}/cerrar/",
            {"metodoPago": "Efectivo", "valorRecibido": 20000},
            format="json",
        )
        self.assertEqual(cerrar.status_code, status.HTTP_200_OK, cerrar.data)
        self.assertEqual(cerrar.data["id"], venta["id"])
        self.assertEqual(cerrar.data["estado"], "cerrada")
        self.assertEqual(cerrar.data["cambio"], 6000)
        self.assertEqual(cerrar.data["cerradaPor"], "cajero_test")
        self.assertEqual(self.stock(self.cuaderno), 9)
        self.assertEqual(self.stock(self.lapiz), 3)

    def test_totales_con_iva_incluido(self):
        venta = self.crear_cerrada(metodoPago="Efectivo", valorRecibido=25000)
        self.assertEqual(venta["subtotal"], 22000)
        self.assertEqual(venta["total"], 22000)  # el IVA NO se suma
        self.assertEqual(venta["ivaPorcentaje"], 19)
        self.assertEqual(venta["ivaIncluido"], 3513)  # 22000 - round(22000 / 1.19)
        self.assertEqual(venta["cambio"], 3000)

    def test_el_backend_ignora_precios_y_totales_del_frontend(self):
        respuesta = self.crear(
            items=[{"productoId": self.cuaderno.id, "cantidad": 1, "precio": 1}],
            subtotal=1, total=1, cambio=999,
        )
        self.assertEqual(respuesta.data["items"][0]["precioUnitario"], 10000)
        self.assertEqual(respuesta.data["total"], 10000)

    def test_producto_repetido_se_suma(self):
        respuesta = self.crear(items=[
            {"productoId": self.lapiz.id, "cantidad": 1},
            {"productoId": self.lapiz.id, "cantidad": 2},
        ])
        self.assertEqual(respuesta.data["items"][0]["cantidad"], 3)

    def test_edicion_en_caliente_se_refleja_al_cerrar(self):
        venta = self.crear().data
        self.client.patch(
            f"/api/productos/{self.cuaderno.id}/edicion-rapida/", {"precio": 12000}, format="json"
        )
        cerrar = self.client.post(
            f"/api/ventas/{venta['id']}/cerrar/", {"metodoPago": "Nequi"}, format="json"
        )
        self.assertEqual(cerrar.data["items"][0]["precioUnitario"], 12000)
        self.assertEqual(cerrar.data["total"], 26000)

    def test_stock_insuficiente_no_cierra_y_nombra_el_producto(self):
        venta = self.crear(items=self.items(cuadernos=1, lapices=6)).data
        cerrar = self.client.post(
            f"/api/ventas/{venta['id']}/cerrar/", {"metodoPago": "Nequi"}, format="json"
        )
        self.assertEqual(cerrar.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Lápiz", cerrar.data["detail"])
        self.assertEqual(Venta.objects.get(pk=venta["id"]).estado, "abierta")
        self.assertEqual(self.stock(self.cuaderno), 10)

    def test_producto_sin_inventario_no_mueve_stock(self):
        self.crear_cerrada(items=[{"productoId": self.impresion.id, "cantidad": 30}])
        self.assertEqual(self.stock(self.impresion), 0)

    def test_pago_debe_requiere_cliente(self):
        sin_cliente = self.crear(cerrar=True, metodoPago="Debe")
        self.assertEqual(sin_cliente.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("clienteId", sin_cliente.data["errores"])
        con_cliente = self.crear(cerrar=True, metodoPago="Debe", clienteId=self.cliente.id)
        self.assertEqual(con_cliente.status_code, status.HTTP_201_CREATED)
        self.assertEqual(con_cliente.data["clienteNombre"], "Ana")

    def test_efectivo_insuficiente(self):
        respuesta = self.crear(cerrar=True, metodoPago="Efectivo", valorRecibido=1000)
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Faltan", respuesta.data["detail"])

    def test_venta_cerrada_no_se_edita_como_abierta(self):
        venta = self.crear_cerrada()
        respuesta = self.client.patch(
            f"/api/ventas/{venta['id']}/", {"items": self.items(cuadernos=1, lapices=0)}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filtro_por_estado(self):
        self.crear()
        self.crear_cerrada()
        abiertas = self.client.get("/api/ventas/?estado=abierta")
        self.assertEqual(len(abiertas.data), 1)
        self.assertEqual(abiertas.data[0]["estado"], "abierta")

    def test_fallo_a_mitad_del_cierre_no_deja_datos_a_medias(self):
        venta = self.crear().data
        with mock.patch(
            "apps.catalogo.models.Producto.save", side_effect=RuntimeError("fallo simulado")
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    f"/api/ventas/{venta['id']}/cerrar/", {"metodoPago": "Nequi"}, format="json"
                )
        self.assertEqual(Venta.objects.get(pk=venta["id"]).estado, "abierta")
        self.assertEqual(self.stock(self.cuaderno), 10)
        self.assertEqual(self.stock(self.lapiz), 5)


class DescuentosEnVentaTests(BaseVentasTest):
    def setUp(self):
        super().setUp()
        self.diez = Descuento.objects.create(nombre="Diez", tipo="PORCENTAJE", valor=10)
        self.grande = Descuento.objects.create(nombre="Grande", tipo="VALOR_FIJO", valor=30000)

    def test_descuento_porcentual_sobre_el_total(self):
        venta = self.crear_cerrada(descuentoId=self.diez.id)
        self.assertEqual(venta["descuentoMonto"], 2200)
        self.assertEqual(venta["total"], 19800)
        self.assertEqual(venta["descuento"]["nombre"], "Diez")

    def test_descuento_que_deja_total_negativo_es_rechazado(self):
        respuesta = self.crear(cerrar=True, metodoPago="Nequi", descuentoId=self.grande.id)
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("descuentoId", respuesta.data["errores"])

    def test_eliminar_descuento_no_altera_ventas_registradas(self):
        venta = self.crear_cerrada(descuentoId=self.diez.id)
        self.client.force_authenticate(self.admin)
        borrar = self.client.delete(f"/api/descuentos/{self.diez.id}/")
        self.assertEqual(borrar.status_code, status.HTTP_204_NO_CONTENT)
        despues = self.client.get(f"/api/ventas/{venta['id']}/").data
        self.assertIsNone(despues["descuentoId"])
        self.assertEqual(despues["descuento"]["nombre"], "Diez")
        self.assertEqual(despues["total"], 19800)


class CorreccionTests(BaseVentasTest):
    def setUp(self):
        super().setUp()
        self.venta = self.crear_cerrada()  # 2 cuadernos + 1 lápiz, Nequi
        self.client.force_authenticate(self.admin)

    def corregir(self, **datos):
        return self.client.post(f"/api/ventas/{self.venta['id']}/corregir/", datos, format="json")

    def test_cajero_no_puede_corregir(self):
        self.client.force_authenticate(self.cajero)
        self.assertEqual(self.corregir(items=self.items()).status_code, status.HTTP_403_FORBIDDEN)

    def test_correccion_ajusta_stock_por_diferencia_y_audita(self):
        self.assertEqual(self.stock(self.cuaderno), 8)
        self.assertEqual(self.stock(self.lapiz), 4)
        respuesta = self.corregir(
            items=[
                {"productoId": self.cuaderno.id, "cantidad": 5},
                {"productoId": self.impresion.id, "cantidad": 1},
            ],
            clienteId=self.cliente.id,
            metodoPago="Debe",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.assertEqual(respuesta.data["id"], self.venta["id"])
        self.assertTrue(respuesta.data["corregida"])
        self.assertEqual(respuesta.data["corregidaPor"], "admin_test")
        self.assertIsNotNone(respuesta.data["corregidaEn"])
        self.assertEqual(respuesta.data["total"], 50500)
        self.assertEqual(respuesta.data["metodoPago"], "Debe")
        self.assertEqual(self.stock(self.cuaderno), 5)  # 8 - 3 unidades adicionales
        self.assertEqual(self.stock(self.lapiz), 5)  # el lápiz retirado vuelve al stock

    def test_correccion_que_deja_stock_negativo_se_rechaza(self):
        respuesta = self.corregir(items=[{"productoId": self.cuaderno.id, "cantidad": 20}])
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Cuaderno", respuesta.data["detail"])
        self.assertEqual(self.stock(self.cuaderno), 8)
        self.assertFalse(Venta.objects.get(pk=self.venta["id"]).corregida)

    def test_venta_abierta_no_se_corrige(self):
        self.client.force_authenticate(self.cajero)
        abierta = self.crear().data
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            f"/api/ventas/{abierta['id']}/corregir/", {"items": self.items()}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)


class ReembolsoTests(BaseVentasTest):
    def setUp(self):
        super().setUp()
        diez = Descuento.objects.create(nombre="Diez", tipo="PORCENTAJE", valor=10)
        self.venta = self.crear_cerrada(descuentoId=diez.id)  # total 19.800
        self.client.force_authenticate(self.admin)

    def reembolsar(self, **datos):
        return self.client.post(f"/api/ventas/{self.venta['id']}/reembolsos/", datos, format="json")

    def test_cajero_no_puede_reembolsar(self):
        self.client.force_authenticate(self.cajero)
        respuesta = self.reembolsar(todo=True)
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_reembolso_parcial_proporcional_al_descuento_y_con_retorno(self):
        respuesta = self.reembolsar(
            items=[{"productoId": self.cuaderno.id, "cantidad": 1, "retornaInventario": True}],
            motivo="Hoja dañada",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["estadoReembolso"], "parcial")
        self.assertEqual(respuesta.data["reembolsos"][0]["total"], 9000)  # 10.000 - 10 %
        self.assertEqual(respuesta.data["reembolsos"][0]["usuario"], "admin_test")
        self.assertEqual(self.stock(self.cuaderno), 9)

    def test_reembolso_total_sin_retorno_devuelve_exactamente_lo_pagado(self):
        self.reembolsar(items=[{"productoId": self.cuaderno.id, "cantidad": 1}])
        respuesta = self.reembolsar(todo=True, retornaInventario=False)
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["estadoReembolso"], "total")
        self.assertEqual(respuesta.data["totalReembolsado"], 19800)
        self.assertEqual(self.stock(self.cuaderno), 9)  # solo volvió el primero
        self.assertEqual(self.stock(self.lapiz), 4)

    def test_no_se_reembolsa_mas_de_lo_vendido(self):
        self.reembolsar(items=[{"productoId": self.cuaderno.id, "cantidad": 2}])
        respuesta = self.reembolsar(items=[{"productoId": self.cuaderno.id, "cantidad": 1}])
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Solo se pueden reembolsar 0", respuesta.data["detail"])

    def test_producto_que_no_pertenece_a_la_venta(self):
        respuesta = self.reembolsar(items=[{"productoId": self.impresion.id, "cantidad": 1}])
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_venta_con_reembolso_ya_no_se_corrige(self):
        self.reembolsar(items=[{"productoId": self.lapiz.id, "cantidad": 1}])
        respuesta = self.client.post(
            f"/api/ventas/{self.venta['id']}/corregir/", {"items": self.items()}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_venta_abierta_no_se_reembolsa(self):
        self.client.force_authenticate(self.cajero)
        abierta = self.crear().data
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(
            f"/api/ventas/{abierta['id']}/reembolsos/", {"todo": True}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
