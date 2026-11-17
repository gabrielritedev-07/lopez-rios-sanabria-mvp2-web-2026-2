from django.contrib import admin

from .models import TurnoCaja


@admin.register(TurnoCaja)
class TurnoCajaAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "estado", "abierto_en", "cerrado_en", "efectivo_esperado", "efectivo_contado", "diferencia")
    list_filter = ("estado", "usuario")
