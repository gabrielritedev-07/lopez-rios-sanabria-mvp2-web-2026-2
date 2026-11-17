"""
Crea (o actualiza) los usuarios iniciales del POS: un administrador y un cajero.

Uso:
    python manage.py crear_usuarios_iniciales
    python manage.py crear_usuarios_iniciales --reset-password   # vuelve a fijar las contraseñas

Los nombres y contraseñas se leen de las variables de entorno POS_ADMIN_USERNAME,
POS_ADMIN_PASSWORD, POS_CAJERO_USERNAME y POS_CAJERO_PASSWORD (ver .env.example).
El comando es idempotente: se puede ejecutar varias veces sin duplicar usuarios.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.usuarios.models import UserProfile

USUARIOS_INICIALES = (
    {
        "rol": UserProfile.Rol.ADMINISTRADOR,
        "username_env": "POS_ADMIN_USERNAME",
        "username_defecto": "admin",
        "password_env": "POS_ADMIN_PASSWORD",
        "password_defecto": "Admin.PyL2026",
        "first_name": "Administrador",
        # El administrador también puede entrar al panel /admin/ de Django.
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "rol": UserProfile.Rol.CAJERO,
        "username_env": "POS_CAJERO_USERNAME",
        "username_defecto": "cajero",
        "password_env": "POS_CAJERO_PASSWORD",
        "password_defecto": "Cajero.PyL2026",
        "first_name": "Cajero",
        "is_staff": False,
        "is_superuser": False,
    },
)


class Command(BaseCommand):
    help = "Crea o actualiza los usuarios iniciales (administrador y cajero) con su rol."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Vuelve a asignar la contraseña configurada aunque el usuario ya exista.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        for datos in USUARIOS_INICIALES:
            username = os.getenv(datos["username_env"], datos["username_defecto"])
            password = os.getenv(datos["password_env"], datos["password_defecto"])

            usuario, creado = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": datos["first_name"],
                    "is_staff": datos["is_staff"],
                    "is_superuser": datos["is_superuser"],
                },
            )
            if creado or options["reset_password"]:
                usuario.set_password(password)
            usuario.is_active = True
            usuario.is_staff = datos["is_staff"]
            usuario.is_superuser = datos["is_superuser"]
            usuario.save()

            UserProfile.objects.update_or_create(user=usuario, defaults={"rol": datos["rol"]})

            accion = "creado" if creado else "actualizado"
            self.stdout.write(
                self.style.SUCCESS(f"Usuario '{username}' {accion} con rol {datos['rol']}.")
            )
