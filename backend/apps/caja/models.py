"""
Turnos de caja y arqueo.

Al abrir el turno el cajero registra la base inicial en efectivo. Al cerrarlo cuenta el
efectivo físico y el sistema compara con lo que debería haber:

    efectivo esperado = base inicial + ventas en efectivo + abonos en efectivo
                        - reembolsos de ventas en efectivo

diferencia = efectivo contado - efectivo esperado  (> 0 sobrante, < 0 faltante).
Solo cuenta lo que hizo el propio usuario durante su turno.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TurnoCaja(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        CERRADO = "cerrado", "Cerrado"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turnos_caja"
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTO)
    abierto_en = models.DateTimeField(default=timezone.now, db_index=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    base_inicial = models.PositiveIntegerField()

    # Fotografía del cierre (en un turno abierto se calculan en vivo).
    cantidad_ventas = models.PositiveIntegerField(default=0)
    ventas_efectivo = models.PositiveIntegerField(default=0)
    ventas_nequi = models.PositiveIntegerField(default=0)
    ventas_debe = models.PositiveIntegerField(default=0)
    abonos_efectivo = models.PositiveIntegerField(default=0)
    abonos_nequi = models.PositiveIntegerField(default=0)
    reembolsos_efectivo = models.PositiveIntegerField(default=0)
    efectivo_esperado = models.IntegerField(default=0)
    efectivo_contado = models.PositiveIntegerField(null=True, blank=True)
    diferencia = models.IntegerField(default=0)
    observaciones = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-abierto_en", "-id"]
        verbose_name = "turno de caja"
        verbose_name_plural = "turnos de caja"
        constraints = [
            # Un usuario solo puede tener un turno abierto a la vez.
            models.UniqueConstraint(
                fields=["usuario"],
                condition=Q(estado="abierto"),
                name="un_turno_abierto_por_usuario",
            ),
            models.CheckConstraint(
                condition=Q(estado="abierto") | Q(cerrado_en__isnull=False, efectivo_contado__isnull=False),
                name="turno_cerrado_tiene_arqueo",
            ),
        ]

    def __str__(self):
        return f"Turno {self.pk} de {self.usuario} ({self.get_estado_display()})"

    @property
    def resultado(self):
        if self.efectivo_contado is None:
            return None
        if self.diferencia > 0:
            return "sobrante"
        if self.diferencia < 0:
            return "faltante"
        return "cuadrado"
