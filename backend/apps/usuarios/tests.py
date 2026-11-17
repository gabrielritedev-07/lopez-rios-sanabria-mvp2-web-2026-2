"""Pruebas de autenticación JWT. Ejecutar: python manage.py test apps.usuarios"""
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from .models import UserProfile

User = get_user_model()


def crear_usuario(username, rol=None, password="Clave.Prueba123"):
    usuario = User.objects.create_user(username=username, password=password)
    if rol:
        UserProfile.objects.create(user=usuario, rol=rol)
    return usuario


class AutenticacionTests(APITestCase):
    def setUp(self):
        crear_usuario("admin_test", UserProfile.Rol.ADMINISTRADOR)
        crear_usuario("cajero_test", UserProfile.Rol.CAJERO)
        crear_usuario("sin_rol")

    def login(self, username, password="Clave.Prueba123"):
        return self.client.post(
            "/api/auth/login/", {"username": username, "password": password}, format="json"
        )

    def test_login_correcto_devuelve_tokens_y_rol(self):
        respuesta = self.login("admin_test")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn("access", respuesta.data)
        self.assertIn("refresh", respuesta.data)
        self.assertEqual(respuesta.data["usuario"]["rol"], "ADMINISTRADOR")

    def test_login_cajero(self):
        respuesta = self.login("cajero_test")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data["usuario"]["rol"], "CAJERO")

    def test_contrasena_incorrecta_responde_401_con_detail(self):
        respuesta = self.login("admin_test", "incorrecta")
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(respuesta.data["detail"])

    def test_usuario_sin_rol_no_puede_entrar(self):
        respuesta = self.login("sin_rol")
        self.assertEqual(respuesta.status_code, status.HTTP_403_FORBIDDEN)

    def test_me_con_token(self):
        access = self.login("cajero_test").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        respuesta = self.client.get("/api/auth/me/")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta.data["username"], "cajero_test")
        self.assertEqual(respuesta.data["rol"], "CAJERO")

    def test_me_sin_token_responde_401(self):
        respuesta = self.client.get("/api/auth/me/")
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_invalido_responde_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer token-falso")
        respuesta = self.client.get("/api/auth/me/")
        self.assertEqual(respuesta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_entrega_nuevo_access(self):
        refresh = self.login("admin_test").data["refresh"]
        respuesta = self.client.post("/api/auth/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertIn("access", respuesta.data)
