"""Pruebas de faltantes. Ejecutar: python manage.py test apps.faltantes"""
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.catalogo.models import Categoria, Producto, Proveedor
from apps.usuarios.models import UserProfile

from .models import Faltante
from .utils import normalizar_nombre

User = get_user_model()


class NormalizacionTests(SimpleTestCase):
    def test_reglas_de_normalizacion(self):
        casos = {
            "Lápices  de Colores": "lapiz de color",
            "lapiz de color": "lapiz de color",
            "CUADERNOS rayados": "cuaderno rayado",
            "Papeles": "papel",
            "Compás": "compas",
            "Piñatas": "piñata",
            "Hojas iris": "hoja iris",
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(normalizar_nombre(entrada), esperado)


class FaltantesTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.admin, rol=UserProfile.Rol.ADMINISTRADOR)
        self.cajero = User.objects.create_user("cajero_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.cajero, rol=UserProfile.Rol.CAJERO)
        categoria = Categoria.objects.create(nombre="Papelería")
        self.cuaderno = Producto.objects.create(
            nombre="Cuaderno", categoria=categoria, precio=10000, seguimiento_inventario=True, stock=0
        )
        self.andina = Proveedor.objects.create(nombre="Distribuidora Andina")
        self.norte = Proveedor.objects.create(nombre="Papeles del Norte")
        self.client.force_authenticate(self.cajero)

    def registrar(self, **datos):
        return self.client.post("/api/faltantes/", datos, format="json")

    def test_cajero_registra_producto_inexistente_en_texto(self):
        respuesta = self.registrar(
            nombre="Lápices de Colores", cantidad=3, tipo="inexistente", proveedorId=self.andina.id
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["nombreNormalizado"], "lapiz de color")
        self.assertEqual(respuesta.data["estado"], "pendiente")
        self.assertEqual(respuesta.data["registradoPor"], "cajero_test")

    def test_registrar_producto_agotado(self):
        respuesta = self.registrar(productoId=self.cuaderno.id, tipo="agotado", cantidad=2)
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["nombre"], "Cuaderno")

    def test_validaciones(self):
        self.assertEqual(self.registrar(tipo="agotado", nombre="Algo").status_code, 400)
        self.assertEqual(self.registrar(tipo="inexistente", productoId=self.cuaderno.id).status_code, 400)
        self.assertEqual(self.registrar(tipo="inexistente").status_code, 400)
        self.assertEqual(self.registrar(tipo="inexistente", nombre="X", cantidad=0).status_code, 400)
        self.assertEqual(self.registrar(nombre="X").status_code, 400)  # sin tipo
        self.assertEqual(Faltante.objects.count(), 0)

    def test_filtros_por_tipo_y_proveedor(self):
        self.registrar(nombre="Témperas", tipo="inexistente", proveedorId=self.andina.id)
        self.registrar(productoId=self.cuaderno.id, tipo="agotado", proveedorId=self.norte.id)
        self.registrar(nombre="Escarcha", tipo="inexistente")
        self.assertEqual(len(self.client.get("/api/faltantes/?tipo=agotado").data), 1)
        self.assertEqual(len(self.client.get(f"/api/faltantes/?proveedor={self.andina.id}").data), 1)
        self.assertEqual(len(self.client.get("/api/faltantes/?proveedor=ninguno").data), 1)
        self.assertEqual(len(self.client.get("/api/faltantes/?q=tempera").data), 1)
        self.assertEqual(self.client.get("/api/faltantes/?tipo=otro").status_code, 400)

    def test_resolver_solo_administrador(self):
        faltante = self.registrar(nombre="Escarcha", tipo="inexistente").data
        url = f"/api/faltantes/{faltante['id']}/resolver/"
        self.assertEqual(self.client.post(url).status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.admin)
        respuesta = self.client.post(url)
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data["estado"], "resuelto")
        self.assertEqual(respuesta.data["resueltoPor"], "admin_test")
        self.assertEqual(self.client.post(url).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(self.client.get("/api/faltantes/?estado=pendiente").data), 0)

    def test_pendientes_agrupados_por_producto_y_proveedor(self):
        self.registrar(nombre="Lápices de colores", cantidad=2, tipo="inexistente", proveedorId=self.andina.id)
        self.registrar(nombre="lapiz de color", cantidad=3, tipo="inexistente", proveedorId=self.andina.id)
        self.registrar(nombre="Lapiz de color", cantidad=1, tipo="inexistente", proveedorId=self.norte.id)
        self.registrar(productoId=self.cuaderno.id, tipo="agotado", cantidad=4, proveedorId=self.andina.id)

        self.assertEqual(self.client.get("/api/faltantes/pendientes/").status_code, 403)
        self.client.force_authenticate(self.admin)
        grupos = self.client.get("/api/faltantes/pendientes/").data
        self.assertEqual(len(grupos), 3)
        primero = grupos[0]
        self.assertEqual(primero["nombreNormalizado"], "lapiz de color")
        self.assertEqual(primero["proveedorNombre"], "Distribuidora Andina")
        self.assertEqual(primero["solicitudes"], 2)
        self.assertEqual(primero["cantidadTotal"], 5)
        self.assertEqual(len(primero["ids"]), 2)
        cuaderno = next(g for g in grupos if g["productoId"] == self.cuaderno.id)
        self.assertEqual(cuaderno["stockActual"], 0)

    def test_proveedor_con_faltantes_no_se_elimina(self):
        self.registrar(nombre="Escarcha", tipo="inexistente", proveedorId=self.norte.id)
        self.client.force_authenticate(self.admin)
        respuesta = self.client.delete(f"/api/proveedores/{self.norte.id}/")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
