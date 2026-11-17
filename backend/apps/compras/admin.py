from django.contrib import admin

from .models import Compra, DetalleCompra


class DetalleCompraInline(admin.TabularInline):
    model = DetalleCompra
    extra = 0


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "proveedor", "total", "registrada_por")
    list_filter = ("proveedor",)
    inlines = [DetalleCompraInline]
