"""Compras a proveedores y sus líneas de detalle."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalogo.models import MarcaTiempo


class Compra(MarcaTiempo):
    # PROTECT: no se puede eliminar un proveedor que tenga compras.
    proveedor = models.ForeignKey(
        "catalogo.Proveedor",
        on_delete=models.PROTECT,
        related_name="compras",
    )
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    total = models.PositiveIntegerField(default=0)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="compras_registradas",
    )

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "compra"
        verbose_name_plural = "compras"

    def __str__(self):
        return f"{self.numero} - {self.proveedor}"

    @property
    def numero(self):
        """Identificador legible usado desde el MVP 2 (CO-001, CO-002...)."""
        return f"CO-{self.pk:03d}" if self.pk else "CO-nueva"


class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        related_name="detalles_compra",
    )
    # Fotografía del producto y del costo al momento de la compra.
    nombre_producto = models.CharField(max_length=150)
    costo_unitario = models.PositiveIntegerField()
    cantidad = models.PositiveIntegerField()
    subtotal = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]
        verbose_name = "detalle de compra"
        verbose_name_plural = "detalles de compra"
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad__gte=1),
                name="detalle_compra_cantidad_minima",
            ),
        ]

    def __str__(self):
        return f"{self.nombre_producto} x {self.cantidad}"
