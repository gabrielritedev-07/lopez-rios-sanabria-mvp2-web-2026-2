"""Filtro reutilizable por rango de fechas: ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD (ambos incluidos)."""
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError


def leer_fecha(request, nombre):
    texto = request.query_params.get(nombre)
    if not texto:
        return None
    try:
        fecha = parse_date(texto)
    except ValueError:
        fecha = None
    if fecha is None:
        raise ValidationError({nombre: "Usa el formato AAAA-MM-DD."})
    return fecha


def rango_fechas(request):
    desde = leer_fecha(request, "desde")
    hasta = leer_fecha(request, "hasta")
    if desde and hasta and desde > hasta:
        raise ValidationError({"desde": "La fecha inicial no puede ser posterior a la final."})
    return desde, hasta


def filtrar_por_fechas(consulta, request, campo="fecha"):
    """Filtra por día en la zona horaria del POS (America/Bogota)."""
    desde, hasta = rango_fechas(request)
    if desde:
        consulta = consulta.filter(**{f"{campo}__date__gte": desde})
    if hasta:
        consulta = consulta.filter(**{f"{campo}__date__lte": hasta})
    return consulta
