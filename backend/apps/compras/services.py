"""Caso de uso: registrar una compra y actualizar el inventario en una sola transacción."""
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone

from apps.catalogo.inventario import bloquear_productos, mover_stock
from apps.catalogo.models import MovimientoInventario

from .models import Compra, DetalleCompra


def fecha_de_compra(fecha):
    """Hoy -> hora actual. Fecha pasada -> mediodía de ese día (hora de Colombia)."""
    if fecha is None or fecha == timezone.localdate():
        return timezone.now()
    return timezone.make_aware(datetime.combine(fecha, time(12, 0)))


@transaction.atomic
def registrar_compra(*, usuario, datos):
    """
    - Guarda la compra y sus líneas con una fotografía del producto y el costo.
    - Actualiza el costo del producto con el último costo de compra.
    - Suma stock solo a los productos que llevan seguimiento de inventario.
    Si algo falla, no se guarda ni la compra ni ningún cambio de stock.
    """
    lineas = datos["items"]
    productos = bloquear_productos(item["producto"].pk for item in lineas)

    compra = Compra.objects.create(
        proveedor=datos["proveedor"],
        fecha=fecha_de_compra(datos.get("fecha")),
        registrada_por=usuario,
        total=sum(item["costo"] * item["cantidad"] for item in lineas),
    )
    DetalleCompra.objects.bulk_create([
        DetalleCompra(
            compra=compra,
            producto=productos[item["producto"].pk],
            nombre_producto=productos[item["producto"].pk].nombre,
            costo_unitario=item["costo"],
            cantidad=item["cantidad"],
            subtotal=item["costo"] * item["cantidad"],
        )
        for item in lineas
    ])

    for item in lineas:
        producto = productos[item["producto"].pk]
        if producto.costo != item["costo"]:
            producto.costo = item["costo"]
            producto.save(update_fields=["costo", "actualizado_en"])
        mover_stock(
            producto,
            item["cantidad"],
            tipo=MovimientoInventario.Tipo.COMPRA,
            usuario=usuario,
            referencia=compra.numero,
            nota=f"Proveedor: {compra.proveedor.nombre}",
        )
    return compra
