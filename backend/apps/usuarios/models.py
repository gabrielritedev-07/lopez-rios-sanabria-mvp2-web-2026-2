from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Perfil 1:1 con el usuario de Django que guarda el rol dentro del POS."""

    class Rol(models.TextChoices):
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
        CAJERO = "CAJERO", "Cajero"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CAJERO)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"

    @property
    def es_administrador(self):
        return self.rol == self.Rol.ADMINISTRADOR
