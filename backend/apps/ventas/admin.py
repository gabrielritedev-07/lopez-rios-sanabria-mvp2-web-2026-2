from django.contrib import admin

from .models import Abono, DetalleReembolso, DetalleVenta, Reembolso, Venta


class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "estado", "metodo_pago", "cliente", "total", "corregida", "estado_reembolso")
    list_filter = ("estado", "metodo_pago", "corregida", "estado_reembolso")
    inlines = [DetalleVentaInline]


class DetalleReembolsoInline(admin.TabularInline):
    model = DetalleReembolso
    extra = 0


@admin.register(Reembolso)
class ReembolsoAdmin(admin.ModelAdmin):
    list_display = ("id", "venta", "fecha", "usuario", "total")
    inlines = [DetalleReembolsoInline]


@admin.register(Abono)
class AbonoAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "cliente", "valor", "metodo_pago", "usuario")
    list_filter = ("metodo_pago",)
