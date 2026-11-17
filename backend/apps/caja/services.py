"""
Cálculos del turno de caja.

Solo cuenta lo que hizo el usuario del turno entre la apertura y el cierre:
- ventas que él cerró (por método de pago),
- abonos de clientes que él registró,
- reembolsos que él registró sobre ventas pagadas en efectivo (salida de efectivo).
"""
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.ventas.models import Abono, Reembolso, Venta

from .models import TurnoCaja


def calcular_resumen(turno, hasta=None):
    hasta = hasta or timezone.now()
    ventas = Venta.objects.filter(
        estado=Venta.Estado.CERRADA,
        cerrada_por=turno.usuario,
        cerrada_en__gte=turno.abierto_en,
        cerrada_en__lte=hasta,
    )
    por_metodo = {
        fila["metodo_pago"]: fila
        for fila in ventas.values("metodo_pago").annotate(total=Sum("total"), cantidad=Count("id"))
    }
    abonos = Abono.objects.filter(usuario=turno.usuario, fecha__gte=turno.abierto_en, fecha__lte=hasta)
    abonos_metodo = {
        fila["metodo_pago"]: fila["total"]
        for fila in abonos.values("metodo_pago").annotate(total=Sum("valor"))
    }
    reembolsos_efectivo = Reembolso.objects.filter(
        usuario=turno.usuario,
        fecha__gte=turno.abierto_en,
        fecha__lte=hasta,
        venta__metodo_pago=Venta.MetodoPago.EFECTIVO,
    ).aggregate(total=Sum("total", default=0))["total"]

    total_de = lambda metodo: (por_metodo.get(metodo) or {}).get("total") or 0  # noqa: E731
    turno.cantidad_ventas = sum(fila["cantidad"] for fila in por_metodo.values())
    turno.ventas_efectivo = total_de(Venta.MetodoPago.EFECTIVO)
    turno.ventas_nequi = total_de(Venta.MetodoPago.NEQUI)
    turno.ventas_debe = total_de(Venta.MetodoPago.DEBE)
    turno.abonos_efectivo = abonos_metodo.get(Abono.MetodoPago.EFECTIVO, 0)
    turno.abonos_nequi = abonos_metodo.get(Abono.MetodoPago.NEQUI, 0)
    turno.reembolsos_efectivo = reembolsos_efectivo
    turno.efectivo_esperado = (
        turno.base_inicial + turno.ventas_efectivo + turno.abonos_efectivo - turno.reembolsos_efectivo
    )
    return turno


def turno_abierto(usuario):
    return TurnoCaja.objects.filter(usuario=usuario, estado=TurnoCaja.Estado.ABIERTO).first()


@transaction.atomic
def abrir_turno(*, usuario, base_inicial):
    if TurnoCaja.objects.select_for_update().filter(usuario=usuario, estado=TurnoCaja.Estado.ABIERTO).exists():
        raise ValidationError({"detail": "Ya tienes un turno de caja abierto. Ciérralo antes de abrir otro."})
    return TurnoCaja.objects.create(usuario=usuario, base_inicial=base_inicial)


@transaction.atomic
def cerrar_turno(*, usuario, efectivo_contado, observaciones=""):
    turno = (
        TurnoCaja.objects.select_for_update()
        .filter(usuario=usuario, estado=TurnoCaja.Estado.ABIERTO)
        .first()
    )
    if turno is None:
        raise ValidationError({"detail": "No tienes un turno de caja abierto."})
    ahora = timezone.now()
    calcular_resumen(turno, ahora)
    turno.efectivo_contado = efectivo_contado
    turno.diferencia = efectivo_contado - turno.efectivo_esperado
    turno.observaciones = observaciones
    turno.estado = TurnoCaja.Estado.CERRADO
    turno.cerrado_en = ahora
    turno.save()
    return turno
