"""Pruebas de compras. Ejecutar: python manage.py test apps.compras"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalogo.models import Categoria, Producto, Proveedor
from apps.usuarios.models import UserProfile

User = get_user_model()


class ComprasTests(APITestCase):
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
        self.impresion = Producto.objects.create(
            nombre="Impresión", categoria=categoria, precio=500, costo=50,
            seguimiento_inventario=False,
        )
        self.proveedor = Proveedor.objects.create(nombre="Distribuidora Andina")
        self.client.force_authenticate(self.admin)

    def comprar(self, **datos):
        datos.setdefault("proveedorId", self.proveedor.id)
        datos.setdefault("items", [
            {"productoId": self.cuaderno.id, "cantidad": 10, "costo": 6500},
            {"productoId": self.impresion.id, "cantidad": 5, "costo": 60},
        ])
        return self.client.post("/api/compras/", datos, format="json")

    def test_registrar_compra_suma_stock_y_actualiza_costo(self):
        respuesta = self.comprar()
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["total"], 65300)
        self.assertEqual(respuesta.data["proveedorNombre"], "Distribuidora Andina")
        self.assertEqual(len(respuesta.data["items"]), 2)
        self.cuaderno.refresh_from_db()
        self.impresion.refresh_from_db()
        self.assertEqual(self.cuaderno.stock, 20)
        self.assertEqual(self.cuaderno.costo, 6500)
        self.assertEqual(self.impresion.stock, 0)  # sin seguimiento de inventario
        self.assertEqual(self.impresion.costo, 60)

    def test_listado_y_detalle(self):
        compra = self.comprar().data
        self.assertEqual(len(self.client.get("/api/compras/").data), 1)
        detalle = self.client.get(f"/api/compras/{compra['id']}/")
        self.assertEqual(detalle.status_code, status.HTTP_200_OK)
        filtrado = self.client.get(f"/api/compras/?proveedor={self.proveedor.id}")
        self.assertEqual(len(filtrado.data), 1)

    def test_cajero_no_accede_a_compras(self):
        self.client.force_authenticate(self.cajero)
        self.assertEqual(self.client.get("/api/compras/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.comprar().status_code, status.HTTP_403_FORBIDDEN)

    def test_validaciones(self):
        self.assertEqual(self.comprar(items=[]).status_code, status.HTTP_400_BAD_REQUEST)
        cero = [{"productoId": self.cuaderno.id, "cantidad": 0, "costo": 100}]
        self.assertEqual(self.comprar(items=cero).status_code, status.HTTP_400_BAD_REQUEST)
        negativo = [{"productoId": self.cuaderno.id, "cantidad": 1, "costo": -1}]
        self.assertEqual(self.comprar(items=negativo).status_code, status.HTTP_400_BAD_REQUEST)
        repetido = [
            {"productoId": self.cuaderno.id, "cantidad": 1, "costo": 100},
            {"productoId": self.cuaderno.id, "cantidad": 2, "costo": 100},
        ]
        self.assertEqual(self.comprar(items=repetido).status_code, status.HTTP_400_BAD_REQUEST)
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertEqual(self.comprar(fecha=manana).status_code, status.HTTP_400_BAD_REQUEST)
        self.cuaderno.refresh_from_db()
        self.assertEqual(self.cuaderno.stock, 10)

    def test_proveedor_con_compras_no_se_elimina(self):
        self.comprar()
        respuesta = self.client.delete(f"/api/proveedores/{self.proveedor.id}/")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
