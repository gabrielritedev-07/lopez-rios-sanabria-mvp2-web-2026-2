from django.contrib import admin

from .models import Faltante


@admin.register(Faltante)
class FaltanteAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "nombre_original", "nombre_normalizado", "cantidad", "tipo", "proveedor", "estado")
    list_filter = ("tipo", "estado", "proveedor")
    search_fields = ("nombre_original", "nombre_normalizado")
