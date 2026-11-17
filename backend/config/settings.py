"""
Configuración del backend del POS Papel y Luna (MVP 3).

Todos los valores sensibles o que cambian entre entornos (desarrollo / producción)
se leen de variables de entorno. En desarrollo se cargan desde backend/.env.
"""
import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(nombre, por_defecto=False):
    valor = os.getenv(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


def env_list(nombre, por_defecto=""):
    return [item.strip() for item in os.getenv(nombre, por_defecto).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Seguridad básica
# --------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "clave-solo-para-desarrollo-no-usar-en-produccion"
    else:
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY en las variables de entorno.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Render define RENDER_EXTERNAL_HOSTNAME (ej. pos-papel-y-luna.onrender.com) automáticamente.
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

if not DEBUG:
    # Render, Railway y similares terminan HTTPS en un proxy delante de Django.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# --------------------------------------------------------------------------
# Aplicaciones
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    # Propias (ver backend/apps/)
    "apps.usuarios",
    "apps.catalogo",
    "apps.ventas",
    "apps.compras",
    "apps.faltantes",
    "apps.reportes",
    "apps.caja",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# Base de datos: PostgreSQL obligatorio, configurado con DATABASE_URL
# --------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ImproperlyConfigured(
        "Define DATABASE_URL (PostgreSQL). Ejemplo: "
        "postgresql://postgres:postgres@localhost:5432/pos_papel_luna"
    )

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=env_bool("DB_SSL_REQUIRE", False),
    )
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Contraseñas
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Idioma y zona horaria (Colombia)
# --------------------------------------------------------------------------
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Archivos estáticos (solo los del admin de Django; el frontend se despliega aparte)
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --------------------------------------------------------------------------
# CORS: solo los orígenes del frontend autorizados
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://127.0.0.1:5500,http://localhost:5500"
)
# El token viaja en el encabezado Authorization (no en cookies).
CORS_ALLOW_CREDENTIALS = False

# --------------------------------------------------------------------------
# Django REST Framework + JWT
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Por defecto todo endpoint exige usuario autenticado; los permisos por rol
    # se agregan en cada vista (apps/*/permissions.py).
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": (
        ("rest_framework.renderers.JSONRenderer", "rest_framework.renderers.BrowsableAPIRenderer")
        if DEBUG
        else ("rest_framework.renderers.JSONRenderer",)
    ),
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
    # Búsqueda en listados: /api/productos/?q=cuaderno
    "SEARCH_PARAM": "q",
    # Formato único de errores: {"detail", "codigo"?, "errores"?} (ver config/exceptions.py)
    "EXCEPTION_HANDLER": "config.exceptions.manejar_excepcion",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=int(os.getenv("JWT_REFRESH_HOURS", "8"))),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

# --------------------------------------------------------------------------
# Reglas de negocio configurables del POS
# --------------------------------------------------------------------------
# Los precios ya incluyen IVA: el porcentaje solo sirve para informar en la
# factura el IVA contenido en el total (total - total / 1.19).
POS_IVA_PORCENTAJE = int(os.getenv("POS_IVA_PORCENTAJE", "19"))
# Días antes del vencimiento en que un producto se marca como "próximo a vencer".
POS_DIAS_ALERTA_VENCIMIENTO = int(os.getenv("POS_DIAS_ALERTA_VENCIMIENTO", "15"))
