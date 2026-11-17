"""Productos solicitados por clientes que no existen en inventario o están agotados."""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.catalogo.models import MarcaTiempo

from .utils import normalizar_nombre


class Faltante(MarcaTiempo):
    class Tipo(models.TextChoices):
        INEXISTENTE = "inexistente", "Producto inexistente"
        AGOTADO = "agotado", "Producto agotado"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        RESUELTO = "resuelto", "Resuelto"

    # Producto del catálogo (obligatorio si está agotado). Si el producto se elimina,
    # el faltante se conserva con su nombre en texto.
    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faltantes",
    )
    # Nombre tal como lo pidió el cliente (o el nombre del producto existente).
    nombre_original = models.CharField(max_length=150)
    # Nombre normalizado para agrupar en reportes; se calcula automáticamente al guardar.
    nombre_normalizado = models.CharField(max_length=150, db_index=True, editable=False)
    cantidad = models.PositiveIntegerField(default=1)
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    # PROTECT: no se puede eliminar un proveedor con faltantes asociados.
    proveedor = models.ForeignKey(
        "catalogo.Proveedor",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="faltantes",
    )
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="faltantes_registrados",
    )
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="faltantes_resueltos",
    )
    resuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "faltante"
        verbose_name_plural = "faltantes"
        constraints = [
            models.CheckConstraint(
                condition=Q(cantidad__gte=1),
                name="faltante_cantidad_minima",
                violation_error_message="La cantidad solicitada debe ser al menos 1.",
            ),
            models.CheckConstraint(
                condition=~Q(nombre_original=""),
                name="faltante_nombre_obligatorio",
                violation_error_message="Indica el producto o descríbelo en texto.",
            ),
            models.CheckConstraint(
                condition=Q(estado="pendiente") | Q(resuelto_en__isnull=False),
                name="faltante_resuelto_tiene_fecha",
            ),
        ]

    def __str__(self):
        return f"{self.nombre_original} x {self.cantidad} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        if self.producto_id and not self.nombre_original:
            self.nombre_original = self.producto.nombre
        self.nombre_original = (self.nombre_original or "").strip()
        self.nombre_normalizado = normalizar_nombre(self.nombre_original)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "nombre_original" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"nombre_normalizado"}
        super().save(*args, **kwargs)
