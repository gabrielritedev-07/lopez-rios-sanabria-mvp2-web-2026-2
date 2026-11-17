"""
Consultas de reportes. Las sumas y conteos los hace PostgreSQL con aggregate/annotate
(SUM, COUNT, GROUP BY), no Python, para que sean rápidas aunque haya muchas ventas.

Convenciones:
- Solo se cuentan ventas CERRADAS. Las abiertas aún no son ventas.
- La fecha de una venta es su fecha de cierre; la de una compra, su fecha de compra.
- Los días se calculan en la hora de Colombia (TIME_ZONE = America/Bogota).
"""
from datetime import timedelta

from django.db.models import Count, F, IntegerField, Sum
from django.db.models.functions import TruncDate

from apps.compras.models import Compra
from apps.faltantes.models import Faltante
from apps.faltantes.services import agrupar_faltantes
from apps.ventas.models import Abono, DetalleReembolso, DetalleVenta, Reembolso, Venta


def en_rango(consulta, campo, desde, hasta):
    return consulta.filter(**{f"{campo}__date__gte": desde, f"{campo}__date__lte": hasta})


def reporte_ventas(desde, hasta):
    ventas = en_rango(Venta.objects.filter(estado=Venta.Estado.CERRADA), "fecha", desde, hasta)
    totales = ventas.aggregate(
        cantidad=Count("id"),
        subtotal=Sum("subtotal", default=0),
        descuentos=Sum("descuento_monto", default=0),
        total=Sum("total", default=0),
        iva=Sum("iva", default=0),
    )
    # Reembolsos hechos dentro del rango (dinero devuelto en esos días).
    reembolsado = en_rango(Reembolso.objects.all(), "fecha", desde, hasta).aggregate(
        total=Sum("total", default=0)
    )["total"]

    por_metodo = (
        ventas.values("metodo_pago")
        .annotate(cantidad=Count("id"), total=Sum("total"))
        .order_by("metodo_pago")
    )
    por_dia = (
        ventas.annotate(dia=TruncDate("fecha"))
        .values("dia")
        .annotate(cantidad=Count("id"), total=Sum("total"))
        .order_by("dia")
    )

    cantidad = totales["cantidad"]
    return {
        "desde": desde,
        "hasta": hasta,
        "cantidadVentas": cantidad,
        "subtotal": totales["subtotal"],
        "descuentos": totales["descuentos"],
        "totalVendido": totales["total"],
        "ivaIncluido": totales["iva"],
        "totalReembolsado": reembolsado,
        "totalNeto": totales["total"] - reembolsado,
        "ticketPromedio": round(totales["total"] / cantidad) if cantidad else 0,
        "porMetodoPago": [
            {"metodoPago": fila["metodo_pago"], "cantidad": fila["cantidad"], "total": fila["total"]}
            for fila in por_metodo
        ],
        "porDia": [
            {"fecha": fila["dia"], "cantidad": fila["cantidad"], "total": fila["total"]}
            for fila in por_dia
        ],
    }


def reporte_productos_mas_vendidos(desde, hasta, limite):
    lineas = en_rango(
        DetalleVenta.objects.filter(venta__estado=Venta.Estado.CERRADA, producto__isnull=False),
        "venta__fecha",
        desde,
        hasta,
    )
    ranking = list(
        lineas.values("producto_id", "producto__nombre")
        .annotate(
            unidades=Sum("cantidad"),
            ingresos=Sum("subtotal"),
            ventas=Count("venta", distinct=True),
        )
        .order_by("-unidades", "-ingresos", "producto__nombre")[:limite]
    )
    # Unidades reembolsadas de esas mismas ventas (consulta aparte para no duplicar sumas).
    reembolsadas = dict(
        DetalleReembolso.objects.filter(detalle_venta__in=lineas)
        .values("detalle_venta__producto_id")
        .annotate(unidades=Sum("cantidad"))
        .values_list("detalle_venta__producto_id", "unidades")
    )
    return {
        "desde": desde,
        "hasta": hasta,
        "productos": [
            {
                "posicion": posicion,
                "productoId": fila["producto_id"],
                "nombre": fila["producto__nombre"],
                "unidadesVendidas": fila["unidades"],
                "unidadesReembolsadas": reembolsadas.get(fila["producto_id"], 0),
                "unidadesNetas": fila["unidades"] - reembolsadas.get(fila["producto_id"], 0),
                "ingresos": fila["ingresos"],
                "ventas": fila["ventas"],
            }
            for posicion, fila in enumerate(ranking, start=1)
        ],
    }


def reporte_compras(desde, hasta):
    compras = en_rango(Compra.objects.select_related("proveedor"), "fecha", desde, hasta)
    totales = compras.aggregate(cantidad=Count("id"), total=Sum("total", default=0))
    por_proveedor = (
        compras.values("proveedor_id", "proveedor__nombre")
        .annotate(cantidad=Count("id"), total=Sum("total"))
        .order_by("-total")
    )
    return {
        "desde": desde,
        "hasta": hasta,
        "cantidadCompras": totales["cantidad"],
        "totalComprado": totales["total"],
        "porProveedor": [
            {
                "proveedorId": fila["proveedor_id"],
                "proveedorNombre": fila["proveedor__nombre"],
                "cantidad": fila["cantidad"],
                "total": fila["total"],
            }
            for fila in por_proveedor
        ],
        "compras": [
            {
                "id": compra.id,
                "numero": compra.numero,
                "fecha": compra.fecha,
                "proveedorNombre": compra.proveedor.nombre,
                "total": compra.total,
            }
            for compra in compras.order_by("-fecha", "-id")
        ],
    }


def reporte_faltantes_frecuentes(desde, hasta, estado, limite):
    consulta = Faltante.objects.all()
    if desde and hasta:
        consulta = en_rango(consulta, "fecha", desde, hasta)
    if estado:
        consulta = consulta.filter(estado=estado)
    grupos = agrupar_faltantes(consulta, por_proveedor=False)[:limite]
    for posicion, grupo in enumerate(grupos, start=1):
        grupo["posicion"] = posicion
    return {"desde": desde, "hasta": hasta, "estado": estado, "faltantes": grupos}


# --------------------------------------------------------------------------
# Indicadores en tiempo real (tablero del administrador)
# --------------------------------------------------------------------------
COSTO_LINEA = Sum(F("costo_unitario") * F("cantidad"), output_field=IntegerField(), default=0)


def ventas_cerradas(desde, hasta):
    return en_rango(Venta.objects.filter(estado=Venta.Estado.CERRADA), "fecha", desde, hasta)


def resumen_dia(fecha):
    """
    KPIs de un día: total vendido, número de ventas, ticket promedio, ganancia estimada
    y desglose por método de pago para el cuadre de caja.

    ganancia estimada = (total vendido - reembolsos del día)
                        - (costo de lo vendido - costo de las unidades reembolsadas)
    Usa el costo guardado en cada línea al momento de vender.
    """
    ventas = ventas_cerradas(fecha, fecha)
    totales = ventas.aggregate(
        cantidad=Count("id"),
        total=Sum("total", default=0),
        descuentos=Sum("descuento_monto", default=0),
    )
    costo_vendido = DetalleVenta.objects.filter(venta__in=ventas).aggregate(c=COSTO_LINEA)["c"]
    reembolsos = en_rango(Reembolso.objects.all(), "fecha", fecha, fecha)
    reembolsado = reembolsos.aggregate(t=Sum("total", default=0))["t"]
    costo_devuelto = DetalleReembolso.objects.filter(reembolso__in=reembolsos).aggregate(
        c=Sum(F("cantidad") * F("detalle_venta__costo_unitario"), output_field=IntegerField(), default=0)
    )["c"]

    por_metodo = {
        fila["metodo_pago"]: fila
        for fila in ventas.values("metodo_pago").annotate(cantidad=Count("id"), total=Sum("total"))
    }
    abonos = {
        fila["metodo_pago"]: fila["total"]
        for fila in en_rango(Abono.objects.all(), "fecha", fecha, fecha)
        .values("metodo_pago")
        .annotate(total=Sum("valor"))
    }
    metodos = []
    for metodo in Venta.MetodoPago.values:
        fila = por_metodo.get(metodo, {})
        metodos.append({
            "metodoPago": metodo,
            "cantidad": fila.get("cantidad", 0),
            "total": fila.get("total") or 0,
            "abonos": abonos.get(metodo, 0),
        })

    cantidad = totales["cantidad"]
    ingresos_netos = totales["total"] - reembolsado
    return {
        "fecha": fecha,
        "totalVendido": totales["total"],
        "cantidadVentas": cantidad,
        "ticketPromedio": round(totales["total"] / cantidad) if cantidad else 0,
        "descuentos": totales["descuentos"],
        "totalReembolsado": reembolsado,
        "costoVendido": costo_vendido - costo_devuelto,
        "gananciaEstimada": ingresos_netos - (costo_vendido - costo_devuelto),
        "porMetodoPago": metodos,
        "totalAbonos": sum(abonos.values()),
        # Dinero que efectivamente entró hoy (sin lo fiado): ventas en efectivo y Nequi + abonos.
        "dineroRecibido": sum(m["total"] for m in metodos if m["metodoPago"] != "Debe") + sum(abonos.values()),
    }


def top_productos(desde, hasta, limite=5):
    """Top por unidades vendidas y top por ganancia bruta (precio - costo) en el rango."""
    lineas = DetalleVenta.objects.filter(
        venta__in=ventas_cerradas(desde, hasta), producto__isnull=False
    )
    agrupado = (
        lineas.values("producto_id", "producto__nombre")
        .annotate(unidades=Sum("cantidad"), ingresos=Sum("subtotal"), costo=COSTO_LINEA)
        .annotate(ganancia=F("ingresos") - F("costo"))
    )

    def fila(posicion, datos):
        return {
            "posicion": posicion,
            "productoId": datos["producto_id"],
            "nombre": datos["producto__nombre"],
            "unidades": datos["unidades"],
            "ingresos": datos["ingresos"],
            "costo": datos["costo"],
            "ganancia": datos["ganancia"],
            "margen": round(datos["ganancia"] * 100 / datos["ingresos"], 1) if datos["ingresos"] else 0,
        }

    por_unidades = agrupado.order_by("-unidades", "-ingresos", "producto__nombre")[:limite]
    por_ganancia = agrupado.order_by("-ganancia", "-unidades", "producto__nombre")[:limite]
    return {
        "desde": desde,
        "hasta": hasta,
        "porUnidades": [fila(i, d) for i, d in enumerate(por_unidades, start=1)],
        "porGanancia": [fila(i, d) for i, d in enumerate(por_ganancia, start=1)],
    }


def tendencia(hasta, dias):
    """Ingresos, costos y ganancia por día (incluye días sin ventas en cero)."""
    desde = hasta - timedelta(days=dias - 1)
    ventas = ventas_cerradas(desde, hasta)
    ingresos = {
        fila["dia"]: fila
        for fila in ventas.annotate(dia=TruncDate("fecha")).values("dia").annotate(
            ingresos=Sum("total"), cantidad=Count("id")
        )
    }
    costos = {
        fila["dia"]: fila["costo"]
        for fila in DetalleVenta.objects.filter(venta__in=ventas)
        .annotate(dia=TruncDate("venta__fecha"))
        .values("dia")
        .annotate(costo=COSTO_LINEA)
    }
    serie = []
    for i in range(dias):
        dia = desde + timedelta(days=i)
        ingreso = (ingresos.get(dia) or {}).get("ingresos") or 0
        costo = costos.get(dia) or 0
        serie.append({
            "fecha": dia,
            "ingresos": ingreso,
            "costos": costo,
            "ganancia": ingreso - costo,
            "ventas": (ingresos.get(dia) or {}).get("cantidad", 0),
        })
    return {"desde": desde, "hasta": hasta, "dias": serie}
