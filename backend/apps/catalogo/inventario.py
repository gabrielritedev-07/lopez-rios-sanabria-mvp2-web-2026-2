"""
Utilidades de inventario compartidas por ventas, correcciones, reembolsos, compras y ajustes.

Siempre se llaman DENTRO de transaction.atomic(). select_for_update() bloquea las
filas de los productos hasta que la transacción termina, así dos cajeros no pueden
descontar el mismo stock al mismo tiempo. Se bloquean en orden de id para evitar
bloqueos cruzados (deadlocks).

Cada cambio de stock queda registrado en el kardex (MovimientoInventario).
"""
from rest_framework.exceptions import ValidationError

from .models import MovimientoInventario, Producto


def bloquear_productos(ids):
    """Devuelve {id: Producto} con las filas bloqueadas. Falla si algún id no existe."""
    ids = set(ids)
    productos = {
        producto.pk: producto
        for producto in Producto.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    }
    inexistentes = ids - productos.keys()
    if inexistentes:
        lista = ", ".join(str(pk) for pk in sorted(inexistentes))
        raise ValidationError({"items": f"No existen productos con id: {lista}."})
    return productos


def validar_stock(productos, requerido, etiqueta="requerido"):
    """
    requerido = {producto_id: unidades que se van a descontar}.
    Solo aplica a productos con seguimiento de inventario. Si falta stock,
    rechaza la operación indicando cada producto afectado.
    """
    problemas = []
    for producto_id, cantidad in requerido.items():
        producto = productos[producto_id]
        if producto.seguimiento_inventario and cantidad > producto.stock:
            problemas.append(
                f"{producto.nombre} (disponible: {producto.stock}, {etiqueta}: {cantidad})"
            )
    if problemas:
        raise ValidationError({"items": "Stock insuficiente: " + "; ".join(problemas) + "."})


def registrar_movimiento(producto, cantidad, stock_anterior, *, tipo, usuario=None, referencia="", nota=""):
    """Escribe una línea del kardex. No modifica el producto."""
    if cantidad == 0:
        return None
    return MovimientoInventario.objects.create(
        producto=producto,
        tipo=tipo,
        cantidad=cantidad,
        stock_anterior=stock_anterior,
        stock_resultante=producto.stock,
        usuario=usuario,
        referencia=referencia,
        nota=nota[:255],
    )


def mover_stock(producto, unidades, *, tipo, usuario=None, referencia="", nota=""):
    """
    Suma (unidades > 0) o resta (unidades < 0) stock si el producto lleva inventario
    y deja el movimiento en el kardex.
    """
    if not producto.seguimiento_inventario or unidades == 0:
        return
    anterior = producto.stock
    producto.stock += unidades
    producto.save(update_fields=["stock", "actualizado_en"])
    registrar_movimiento(
        producto, unidades, anterior, tipo=tipo, usuario=usuario, referencia=referencia, nota=nota
    )
