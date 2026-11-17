from django.contrib.auth import get_user_model
from rest_framework import exceptions, serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .permissions import obtener_rol


class UsuarioSerializer(serializers.ModelSerializer):
    """Datos públicos del usuario autenticado que necesita el frontend."""

    nombre = serializers.SerializerMethodField()
    rol = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "nombre", "rol"]

    def get_nombre(self, user):
        return user.get_full_name() or user.username

    def get_rol(self, user):
        return obtener_rol(user)


class LoginSerializer(TokenObtainPairSerializer):
    """
    Recibe {username, password} y devuelve {access, refresh, usuario}.
    Agrega el username y el rol como datos (claims) dentro del token.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["rol"] = obtener_rol(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)  # valida usuario/contraseña y deja self.user
        if obtener_rol(self.user) is None:
            raise exceptions.PermissionDenied("Tu usuario no tiene un rol asignado en el POS.")
        data["usuario"] = UsuarioSerializer(self.user).data
        return data
