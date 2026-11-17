"""
Permisos por rol del POS.

El rol siempre se consulta en la base de datos (UserProfile) en cada petición.
El rol que viaja dentro del token JWT solo lo usa el frontend para mostrar u
ocultar opciones; el backend nunca confía en él para autorizar.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import UserProfile

ADMINISTRADOR = UserProfile.Rol.ADMINISTRADOR
CAJERO = UserProfile.Rol.CAJERO

MENSAJE_SOLO_ADMIN = "Esta acción solo está permitida para el administrador."


def obtener_rol(user):
    """Devuelve el rol del usuario en el POS, o None si no tiene uno asignado."""
    if not user or not user.is_authenticated:
        return None
    perfil = getattr(user, "perfil", None)
    if perfil is not None:
        return perfil.rol
    # Un superusuario creado con createsuperuser sin perfil se trata como administrador.
    if user.is_superuser:
        return ADMINISTRADOR
    return None


class TieneRolPOS(BasePermission):
    """Cualquier usuario autenticado con rol (administrador o cajero)."""

    message = "Tu usuario no tiene un rol asignado en el POS."

    def has_permission(self, request, view):
        return obtener_rol(request.user) is not None


class EsAdministrador(BasePermission):
    """Solo administrador, para cualquier método HTTP."""

    message = MENSAJE_SOLO_ADMIN

    def has_permission(self, request, view):
        return obtener_rol(request.user) == ADMINISTRADOR


class LecturaTodosEscrituraAdministrador(BasePermission):
    """
    GET para cualquier rol del POS; POST, PUT, PATCH y DELETE solo para administrador.
    Ej.: el cajero consulta productos y categorías, pero no los crea ni los borra.
    """

    message = MENSAJE_SOLO_ADMIN

    def has_permission(self, request, view):
        rol = obtener_rol(request.user)
        if rol is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return rol == ADMINISTRADOR


def es_admin_en_contexto(serializer):
    """True si la petición la hace un administrador (o si no hay petición: uso interno)."""
    request = serializer.context.get("request")
    if request is None:
        return True
    return obtener_rol(request.user) == ADMINISTRADOR


class OcultarCostosMixin:
    """
    Quita del JSON los campos de costo y margen cuando quien consulta es un cajero.
    Solo el administrador ve costos, márgenes y ganancias.
    """

    campos_costo = ()

    def to_representation(self, instancia):
        datos = super().to_representation(instancia)
        if not es_admin_en_contexto(self):
            for campo in self.campos_costo:
                datos.pop(campo, None)
        return datos
