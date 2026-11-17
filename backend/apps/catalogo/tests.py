"""Pruebas del CRUD del catálogo y de permisos por rol. Ejecutar: python manage.py test apps.catalogo"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.usuarios.models import UserProfile

from .models import Categoria, Producto

User = get_user_model()


class BaseCatalogoTest(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.admin, rol=UserProfile.Rol.ADMINISTRADOR)
        self.cajero = User.objects.create_user("cajero_test", password="Clave.Prueba123")
        UserProfile.objects.create(user=self.cajero, rol=UserProfile.Rol.CAJERO)
        self.categoria = Categoria.objects.create(nombre="Cuadernos")
        self.producto = Producto.objects.create(
            nombre="Cuaderno rayado",
            categoria=self.categoria,
            precio=5000,
            costo=3000,
            seguimiento_inventario=True,
            stock=10,
        )

    def como(self, usuario):
        self.client.force_authenticate(user=usuario)


class PermisosTests(BaseCatalogoTest):
    def test_sin_autenticacion_responde_401(self):
        respuesta = self.client.get("/api/productos/")
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cajero_consulta_productos(self):
        self.como(self.cajero)
        respuesta = self.client.get("/api/productos/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(respuesta.data), 1)

    def test_cajero_no_crea_productos(self):
        self.como(self.cajero)
        respuesta = self.client.post(
            "/api/productos/",
            {"nombre": "Lápiz", "categoriaId": self.categoria.id, "precio": 1000},
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_cajero_no_elimina_categorias(self):
        self.como(self.cajero)
        respuesta = self.client.delete(f"/api/categorias/{self.categoria.id}/")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_cajero_no_gestiona_descuentos_pero_si_los_consulta(self):
        self.como(self.cajero)
        crear = self.client.post(
            "/api/descuentos/", {"nombre": "X", "tipo": "PORCENTAJE", "valor": 10}, format="json"
        )
        self.assertEqual(crear.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get("/api/descuentos/").status_code, status.HTTP_200_OK)

    def test_cajero_no_crea_proveedores(self):
        self.como(self.cajero)
        respuesta = self.client.post("/api/proveedores/", {"nombre": "Distribuidora"}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_cajero_gestiona_clientes(self):
        self.como(self.cajero)
        respuesta = self.client.post(
            "/api/clientes/", {"nombre": "Ana", "telefono": "300 123 4567"}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED)


class ProductosTests(BaseCatalogoTest):
    def setUp(self):
        super().setUp()
        self.como(self.admin)

    def test_admin_crea_producto_con_nombres_de_la_guia(self):
        respuesta = self.client.post(
            "/api/productos/",
            {
                "nombre": "Lápiz HB",
                "categoriaId": self.categoria.id,
                "precio": 1200,
                "costo": 700,
                "seguimientoInventario": True,
                "stock": 50,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_201_CREATED, respuesta.data)
        self.assertEqual(respuesta.data["categoriaNombre"], "Cuadernos")
        self.assertTrue(respuesta.data["seguimientoInventario"])
        self.assertIsNone(respuesta.data["codigo"])

    def test_precio_negativo_es_rechazado(self):
        respuesta = self.client.post(
            "/api/productos/",
            {"nombre": "X", "categoriaId": self.categoria.id, "precio": -5},
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("precio", respuesta.data["errores"])
        self.assertIn("precio", respuesta.data["detail"])

    def test_campos_obligatorios(self):
        respuesta = self.client.post("/api/productos/", {}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        for campo in ("nombre", "categoriaId", "precio"):
            self.assertIn(campo, respuesta.data["errores"])

    def test_nombre_en_blanco_es_rechazado(self):
        respuesta = self.client.patch(
            f"/api/productos/{self.producto.id}/", {"nombre": "   "}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_codigo_duplicado_es_rechazado_y_vacio_se_permite_varias_veces(self):
        datos = {"nombre": "A", "categoriaId": self.categoria.id, "precio": 100, "codigo": "ABC"}
        self.assertEqual(self.client.post("/api/productos/", datos, format="json").status_code, 201)
        datos["codigo"] = "abc"
        self.assertEqual(self.client.post("/api/productos/", datos, format="json").status_code, 400)
        datos["codigo"] = ""
        self.assertEqual(self.client.post("/api/productos/", datos, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/productos/", datos, format="json").status_code, 201)

    def test_busqueda_y_filtro_por_categoria(self):
        otra = Categoria.objects.create(nombre="Lapiceros")
        Producto.objects.create(nombre="Lapicero azul", categoria=otra, precio=1500)
        self.assertEqual(len(self.client.get("/api/productos/?q=cuaderno").data), 1)
        self.assertEqual(len(self.client.get(f"/api/productos/?categoria={otra.id}").data), 1)

    def test_eliminar_producto_sin_registros(self):
        respuesta = self.client.delete(f"/api/productos/{self.producto.id}/")
        self.assertEqual(respuesta.status_code, status.HTTP_204_NO_CONTENT)


class EdicionRapidaTests(BaseCatalogoTest):
    def test_cajero_edita_precio_pero_no_stock(self):
        self.como(self.cajero)
        respuesta = self.client.patch(
            f"/api/productos/{self.producto.id}/edicion-rapida/",
            {"precio": 5500, "stock": 999, "seguimientoInventario": False},
            format="json",
        )
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.data)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.precio, 5500)
        self.assertEqual(self.producto.stock, 10)
        self.assertTrue(self.producto.seguimiento_inventario)

    def test_cajero_no_usa_patch_normal(self):
        self.como(self.cajero)
        respuesta = self.client.patch(
            f"/api/productos/{self.producto.id}/", {"precio": 1}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)


class IntegridadTests(BaseCatalogoTest):
    def setUp(self):
        super().setUp()
        self.como(self.admin)

    def test_categoria_con_productos_no_se_elimina(self):
        respuesta = self.client.delete(f"/api/categorias/{self.categoria.id}/")
        self.assertEqual(respuesta.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(respuesta.data["codigo"], "registros_asociados")
        self.assertTrue(Categoria.objects.filter(pk=self.categoria.pk).exists())

    def test_categoria_vacia_si_se_elimina(self):
        vacia = Categoria.objects.create(nombre="Temporal")
        respuesta = self.client.delete(f"/api/categorias/{vacia.id}/")
        self.assertEqual(respuesta.status_code, status.HTTP_204_NO_CONTENT)

    def test_nombre_de_categoria_unico_sin_importar_mayusculas(self):
        respuesta = self.client.post("/api/categorias/", {"nombre": "  cuadernos "}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_telefono_invalido(self):
        respuesta = self.client.post(
            "/api/clientes/", {"nombre": "Ana", "telefono": "abc"}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)


class DescuentosTests(BaseCatalogoTest):
    def setUp(self):
        super().setUp()
        self.como(self.admin)

    def test_crear_descuentos_validos(self):
        porcentaje = {"nombre": "Estudiantes", "tipo": "PORCENTAJE", "valor": 10}
        fijo = {"nombre": "Bono 2000", "tipo": "VALOR_FIJO", "valor": 2000}
        self.assertEqual(self.client.post("/api/descuentos/", porcentaje, format="json").status_code, 201)
        self.assertEqual(self.client.post("/api/descuentos/", fijo, format="json").status_code, 201)

    def test_porcentaje_mayor_a_100(self):
        datos = {"nombre": "Error", "tipo": "PORCENTAJE", "valor": 150}
        respuesta = self.client.post("/api/descuentos/", datos, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("valor", respuesta.data["errores"])

    def test_valor_cero(self):
        datos = {"nombre": "Cero", "tipo": "VALOR_FIJO", "valor": 0}
        respuesta = self.client.post("/api/descuentos/", datos, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_tipo_invalido(self):
        datos = {"nombre": "Raro", "tipo": "OTRO", "valor": 5}
        respuesta = self.client.post("/api/descuentos/", datos, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cambiar_a_porcentaje_valida_con_valor_guardado(self):
        creado = self.client.post(
            "/api/descuentos/", {"nombre": "Bono", "tipo": "VALOR_FIJO", "valor": 5000}, format="json"
        ).data
        respuesta = self.client.patch(
            f"/api/descuentos/{creado['id']}/", {"tipo": "PORCENTAJE"}, format="json"
        )
        self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
