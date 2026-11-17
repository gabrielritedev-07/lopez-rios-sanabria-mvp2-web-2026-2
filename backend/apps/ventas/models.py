"""
Ventas, líneas de venta, reembolsos y líneas de reembolso.

Decisiones de diseño:
- Las líneas se guardan en tablas de detalle (DetalleVenta, DetalleReembolso),
  no como JSON en una columna. La API las devolverá como arreglo "items".
- Cada línea guarda una "fotografía" del producto al momento de vender
  (nombre, precio y costo), así el histórico no cambia si luego se edita el producto.
- La venta guarda una fotografía del descuento aplicado (nombre, tipo, valor y monto).
  Si el descuento se borra del catálogo, la FK queda en NULL y la venta no cambia.
- Corrección: la venta conserva su id y se marca con corregida / corregida_por / corregida_en.
- Todos los cálculos (subtotal, descuento, IVA, total, cambio, reembolsos) los hace el backend
  (ver services.py). Los precios ya incluyen IVA: total = subtotal - descuento.
"""
from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.catalogo.models import Descuento, MarcaTiempo


class Venta(MarcaTiempo):
    class Estado(models.TextChoices):
        ABIERTA = "abierta", "Abierta"
        CERRADA = "cerrada", "Cerrada"

    class MetodoPago(models.TextChoices):
        EFECTIVO = "Efectivo", "Efectivo"
        NEQUI = "Nequi", "Nequi"
        DEBE = "Debe", "Debe"

    class EstadoReembolso(models.TextChoices):
        NINGUNO = "ninguno", "Sin reembolsos"
        PARCIAL = "parcial", "Reembolso parcial"
        TOTAL = "total", "Reembolso total"

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.ABIERTA, db_index=True
    )
    # Fecha de la venta; al cerrarla se actualiza con la fecha de cierre. Se usa en reportes.
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    cliente = models.ForeignKey(
        "catalogo.Cliente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ventas",
    )
    metodo_pago = models.CharField(
        max_length=10, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO
    )

    # --- Totales (calculados en el backend) ---
    subtotal = models.PositiveIntegerField(default=0)

    # --- Descuento: referencia + fotografía ---
    descuento = models.ForeignKey(
        "catalogo.Descuento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventas",
    )
    descuento_nombre = models.CharField(max_length=100, blank=True)
    descuento_tipo = models.CharField(max_length=10, choices=Descuento.Tipo.choices, blank=True)
    descuento_valor = models.PositiveIntegerField(default=0)
    descuento_monto = models.PositiveIntegerField(default=0)

    # Los precios ya incluyen IVA: `iva` es informativo (IVA contenido en el total).
    iva_porcentaje = models.PositiveSmallIntegerField(default=19)
    iva = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    # --- Pago ---
    valor_recibido = models.PositiveIntegerField(default=0)
    cambio = models.PositiveIntegerField(default=0)

    # --- Auditoría ---
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ventas_creadas",
    )
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ventas_cerradas",
    )
    cerrada_en = models.DateTimeField(null=True, blank=True)
    corregida = models.BooleanField(default=False)
    corregida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ventas_corregidas",
    )
    corregida_en = models.DateTimeField(null=True, blank=True)
    estado_reembolso = models.CharField(
        max_length=10, choices=EstadoReembolso.choices, default=EstadoReembolso.NINGUNO
    )

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "venta"
        verbose_name_plural = "ventas"
        constraints = [
            models.CheckConstraint(
                condition=Q(descuento_monto__lte=F("subtotal")),
                name="venta_descuento_no_supera_subtotal",
                violation_error_message="El descuento no puede dejar el total en negativo.",
            ),
            models.CheckConstraint(
                condition=~Q(estado="cerrada", metodo_pago="Debe") | Q(cliente__isnull=False),
                name="venta_debe_requiere_cliente",
                violation_error_message="Las ventas con pago Debe requieren un cliente.",
            ),
            models.CheckConstraint(
                condition=Q(estado="abierta") | Q(cerrada_en__isnull=False),
                name="venta_cerrada_tiene_fecha_cierre",
            ),
            models.CheckConstraint(
                condition=Q(corregida=False)
                | Q(corregida_por__isnull=False, corregida_en__isnull=False),
                name="venta_correccion_auditada",
                violation_error_message="Una venta corregida debe registrar quién y cuándo.",
            ),
        ]

    def __str__(self):
        return f"{self.numero} ({self.get_estado_display()})"

    @property
    def numero(self):
        """Identificador legible usado en el POS desde el MVP 2 (V-001, V-002...)."""
        return f"V-{self.pk:03d}" if self.pk else "V-nueva"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    # NULL = ítem libre o servicio rápido (fotocopias, anillados...): no mueve inventario.
    producto = models.ForeignKey(
        "catalogo.Producto",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="detalles_venta",
    )
    # Fotografía del producto al momento de la venta.
    nombre_producto = models.CharField(max_length=150)
    precio_unitario = models.PositiveIntegerField()
    costo_unitario = models.PositiveIntegerField(default=0)
    cantidad = models.PositiveIntegerField()
    subtotal = models.PositiveIntegerField()

    class Meta:
        ordering = ["id"]
        verbose_name = "detalle de venta"
        verbose_name_plural = "detalles de venta"
        constraints = [
            models.UniqueConstraint(
                fields=["venta", "producto"],
                name="detalle_venta_producto_unico",
                violation_error_message="El producto ya está en la venta; ajusta la cantidad.",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gte=1),
                name="detalle_venta_cantidad_minima",
            ),
        ]

    def __str__(self):
        return f"{self.nombre_producto} x {self.cantidad}"

    @property
    def es_libre(self):
        return self.producto_id is None


class Reembolso(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.PROTECT, related_name="reembolsos")
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reembolsos",
    )
    # Valor devuelto al cliente, ya prorrateado según el descuento e IVA de la venta.
    total = models.PositiveIntegerField(default=0)
    motivo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "reembolso"
        verbose_name_plural = "reembolsos"

    def __str__(self):
        return f"Reembolso {self.pk} de {self.venta.numero}"


class DetalleReembolso(models.Model):
    reembolso = models.ForeignKey(Reembolso, on_delete=models.CASCADE, related_name="items")
    detalle_venta = models.ForeignKey(
        DetalleVenta,
        on_delete=models.PROTECT,
        related_name="reembolsos",
    )
    cantidad = models.PositiveIntegerField()
    valor = models.PositiveIntegerField()
    retorna_inventario = models.BooleanField(default=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "detalle de reembolso"
        verbose_name_plural = "detalles de reembolso"
        constraints = [
            models.UniqueConstraint(
                fields=["reembolso", "detalle_venta"],
                name="detalle_reembolso_linea_unica",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gte=1),
                name="detalle_reembolso_cantidad_minima",
            ),
        ]

    def __str__(self):
        return f"{self.detalle_venta.nombre_producto} x {self.cantidad}"


class Abono(models.Model):
    """
    Pago parcial o total de la deuda ("Debe") de un cliente.
    Saldo del cliente = ventas cerradas en Debe - reembolsos de esas ventas - abonos.
    """

    class MetodoPago(models.TextChoices):
        EFECTIVO = "Efectivo", "Efectivo"
        NEQUI = "Nequi", "Nequi / transferencia"

    cliente = models.ForeignKey("catalogo.Cliente", on_delete=models.PROTECT, related_name="abonos")
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    valor = models.PositiveIntegerField()
    metodo_pago = models.CharField(max_length=10, choices=MetodoPago.choices, default=MetodoPago.EFECTIVO)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="abonos_registrados",
    )
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "abono"
        verbose_name_plural = "abonos"
        constraints = [
            models.CheckConstraint(condition=Q(valor__gt=0), name="abono_valor_positivo"),
        ]

    def __str__(self):
        return f"Abono {self.valor} de {self.cliente}"
