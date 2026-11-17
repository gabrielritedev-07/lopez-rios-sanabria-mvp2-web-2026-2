"""
Cartera de clientes (ventas a crédito "Debe") y abonos.

saldo = total de ventas CERRADAS con pago Debe
        - reembolsos de esas ventas (reducen la deuda, no salen de caja)
        - abonos registrados

Las sumas se hacen en PostgreSQL con subconsultas, así el listado de clientes trae
el saldo de todos en una sola consulta.
"""
from django.db import transaction
from django.db.models import F, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

from apps.catalogo.models import Cliente

from .models import Abono, Reembolso, Venta


def _suma(consulta, agrupar_por, campo):
    subconsulta = consulta.order_by().values(agrupar_por).annotate(t=Sum(campo)).values("t")[:1]
    return Coalesce(Subquery(subconsulta, output_field=IntegerField()), Value(0))


def ventas_fiadas():
    return Venta.objects.filter(estado=Venta.Estado.CERRADA, metodo_pago=Venta.MetodoPago.DEBE)


def anotar_saldo(clientes):
    """Agrega total_fiado, total_reembolsado, total_abonado y saldo_pendiente a cada cliente."""
    return clientes.annotate(
        total_fiado=_suma(ventas_fiadas().filter(cliente=OuterRef("pk")), "cliente", "total"),
        total_reembolsado=_suma(
            Reembolso.objects.filter(
                venta__cliente=OuterRef("pk"),
                venta__estado=Venta.Estado.CERRADA,
                venta__metodo_pago=Venta.MetodoPago.DEBE,
            ),
            "venta__cliente",
            "total",
        ),
        total_abonado=_suma(Abono.objects.filter(cliente=OuterRef("pk")), "cliente", "valor"),
    ).annotate(saldo_pendiente=F("total_fiado") - F("total_reembolsado") - F("total_abonado"))


def cliente_con_saldo(cliente_id):
    return anotar_saldo(Cliente.objects.filter(pk=cliente_id)).get()


def resumen_cartera(cliente_id):
    cliente = cliente_con_saldo(cliente_id)
    ventas = (
        ventas_fiadas()
        .filter(cliente=cliente)
        .annotate(reembolsado=_suma(Reembolso.objects.filter(venta=OuterRef("pk")), "venta", "total"))
        .order_by("-fecha")
    )
    return {
        "clienteId": cliente.id,
        "clienteNombre": cliente.nombre,
        "totalFiado": cliente.total_fiado,
        "totalReembolsado": cliente.total_reembolsado,
        "totalAbonado": cliente.total_abonado,
        "saldo": cliente.saldo_pendiente,
        "ventas": [
            {
                "id": v.id,
                "numero": v.numero,
                "fecha": v.fecha,
                "total": v.total,
                "reembolsado": v.reembolsado,
            }
            for v in ventas
        ],
        "abonos": list(cliente.abonos.select_related("usuario").order_by("-fecha", "-id")),
    }


@transaction.atomic
def registrar_abono(*, usuario, cliente_id, datos):
    # Bloquea al cliente para que dos abonos simultáneos no superen la deuda.
    Cliente.objects.select_for_update().get(pk=cliente_id)
    cliente = cliente_con_saldo(cliente_id)
    if cliente.saldo_pendiente <= 0:
        raise ValidationError({"detail": f"{cliente.nombre} no tiene saldo pendiente."})
    if datos["valor"] > cliente.saldo_pendiente:
        raise ValidationError({
            "valor": f"El abono no puede superar el saldo pendiente (${cliente.saldo_pendiente:,})."
            .replace(",", ".")
        })
    return Abono.objects.create(
        cliente=cliente,
        valor=datos["valor"],
        metodo_pago=datos["metodo_pago"],
        nota=datos.get("nota", ""),
        usuario=usuario,
    )
