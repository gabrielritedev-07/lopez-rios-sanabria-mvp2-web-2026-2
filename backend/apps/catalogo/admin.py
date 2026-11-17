from django.contrib import admin

from .models import Categoria, Cliente, Descuento, MovimientoInventario, Producto, Proveedor


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre")
    search_fields = ("nombre",)


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "telefono", "correo")
    search_fields = ("nombre", "telefono", "correo")


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "telefono", "correo")
    search_fields = ("nombre", "telefono", "correo")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("id", "codigo", "nombre", "categoria", "precio", "costo", "seguimiento_inventario", "stock", "stock_minimo", "fecha_vencimiento")
    list_filter = ("categoria", "seguimiento_inventario")
    search_fields = ("nombre", "codigo")


@admin.register(Descuento)
class DescuentoAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "tipo", "valor")
    list_filter = ("tipo",)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ("fecha", "producto", "tipo", "cantidad", "stock_resultante", "usuario", "referencia")
    list_filter = ("tipo",)
    search_fields = ("producto__nombre", "referencia")
