"""Rutas globales del backend. Toda la API vive bajo /api/ (ver backend/API.md)."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def salud(request):
    """Endpoint público para comprobar que la API está desplegada y responde."""
    return JsonResponse({"estado": "ok", "servicio": "API POS Papel y Luna"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/salud/", salud, name="salud"),
    path("api/auth/", include("apps.usuarios.urls")),
    path("api/", include("apps.catalogo.urls")),
    path("api/", include("apps.ventas.urls")),
    path("api/", include("apps.compras.urls")),
    path("api/", include("apps.faltantes.urls")),
    path("api/reportes/", include("apps.reportes.urls")),
    path("api/caja/", include("apps.caja.urls")),
]
