"""
Entidades maestras del POS: categorías, clientes, proveedores, productos y descuentos.

Reglas de integridad que se garantizan en la propia base de datos:
- Montos en pesos enteros y nunca negativos (PositiveIntegerField crea un CHECK >= 0).
- Una categoría con productos no se puede eliminar (on_delete=PROTECT).
- Clientes y proveedores se protegen desde las tablas que los referencian
  (ventas, compras, faltantes) con on_delete=PROTECT.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class MarcaTiempo(models.Model):
    """Campos de auditoría comunes. Abstracta: no crea tabla propia."""

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Categoria(MarcaTiempo):
    nombre = models.CharField(max_length=100)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="categoria_nombre_unico",
                violation_error_message="Ya existe una categoría con ese nombre.",
            ),
        ]

    def __str__(self):
        return self.nombre


class Contacto(MarcaTiempo):
    """Base abstracta para clientes y proveedores (mismos campos en la Guía P2.2)."""

    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=30, blank=True)
    correo = models.EmailField(blank=True)

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Cliente(Contacto):
    class Meta(Contacto.Meta):
        verbose_name = "cliente"
        verbose_name_plural = "clientes"


class Proveedor(Contacto):
    class Meta(Contacto.Meta):
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"


class Producto(MarcaTiempo):
    # Código opcional; si se escribe, no se puede repetir (NULL sí se puede repetir).
    codigo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="productos",
    )
    precio = models.PositiveIntegerField(help_text="Precio de venta en pesos.")
    costo = models.PositiveIntegerField(default=0, help_text="Último costo de compra en pesos.")
    seguimiento_inventario = models.BooleanField(
        default=False,
        help_text="Si es falso, las ventas y compras no modifican el stock (ej. servicios).",
    )
    # PositiveIntegerField: la base de datos rechaza cualquier stock negativo.
    stock = models.PositiveIntegerField(default=0)
    # Punto de reorden: con stock igual o menor se muestra "Stock bajo".
    stock_minimo = models.PositiveIntegerField(default=5)
    # Opcional; útil sobre todo para la dulcería.
    fecha_vencimiento = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def __str__(self):
        return self.nombre

    @property
    def estado_stock(self):
        """None si no lleva inventario; si no 'agotado', 'bajo' u 'ok'."""
        if not self.seguimiento_inventario:
            return None
        if self.stock == 0:
            return "agotado"
        if self.stock <= self.stock_minimo:
            return "bajo"
        return "ok"


class MovimientoInventario(models.Model):
    """
    Kardex: cada entrada o salida de stock de un producto con inventario.
    cantidad > 0 entra mercancía; cantidad < 0 sale.
    """

    class Tipo(models.TextChoices):
        INICIAL = "INICIAL", "Saldo inicial"
        AJUSTE = "AJUSTE", "Ajuste manual"
        COMPRA = "COMPRA", "Compra"
        VENTA = "VENTA", "Venta"
        CORRECCION = "CORRECCION", "Corrección de venta"
        REEMBOLSO = "REEMBOLSO", "Reembolso"

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="movimientos")
    fecha = models.DateTimeField(default=timezone.now, db_index=True)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    cantidad = models.IntegerField()
    stock_anterior = models.PositiveIntegerField()
    stock_resultante = models.PositiveIntegerField()
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_inventario",
    )
    # Documento que originó el movimiento (V-012, CO-003...).
    referencia = models.CharField(max_length=30, blank=True)
    nota = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        verbose_name = "movimiento de inventario"
        verbose_name_plural = "movimientos de inventario"
        constraints = [
            models.CheckConstraint(
                condition=~Q(cantidad=0),
                name="movimiento_cantidad_distinta_de_cero",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.cantidad:+d} · {self.producto}"


class Descuento(MarcaTiempo):
    """Catálogo reutilizable de descuentos. Se aplica al total de la venta, uno por venta."""

    class Tipo(models.TextChoices):
        PORCENTAJE = "PORCENTAJE", "Porcentaje"
        VALOR_FIJO = "VALOR_FIJO", "Valor fijo"

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    # Porcentaje: 1 a 100. Valor fijo: pesos enteros mayores que 0.
    valor = models.PositiveIntegerField()

    class Meta:
        ordering = ["nombre"]
        verbose_name = "descuento"
        verbose_name_plural = "descuentos"
        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="descuento_nombre_unico",
                violation_error_message="Ya existe un descuento con ese nombre.",
            ),
            models.CheckConstraint(
                condition=Q(valor__gt=0),
                name="descuento_valor_positivo",
                violation_error_message="El valor del descuento debe ser mayor que 0.",
            ),
            models.CheckConstraint(
                condition=~Q(tipo="PORCENTAJE") | Q(valor__lte=100),
                name="descuento_porcentaje_max_100",
                violation_error_message="Un descuento porcentual no puede superar el 100 %.",
            ),
        ]

    def __str__(self):
        sufijo = "%" if self.tipo == self.Tipo.PORCENTAJE else " COP"
        return f"{self.nombre} ({self.valor}{sufijo})"
