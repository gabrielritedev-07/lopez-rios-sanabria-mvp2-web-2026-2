"""
Reportes básicos (solo administrador). Todos aceptan ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD
(ambos días incluidos; un solo día = desde y hasta iguales).

GET /api/reportes/ventas/                  ventas totales del rango (por defecto: hoy)
GET /api/reportes/productos-mas-vendidos/  ranking del rango (?limite=10; por defecto: hoy)
GET /api/reportes/compras/                 compras del rango (por defecto: hoy)
GET /api/reportes/faltantes-frecuentes/    productos más solicitados (?limite=10, ?estado=;
                                           sin fechas = todo el historial)

Tablero en tiempo real:
GET /api/reportes/resumen-dia/?fecha=      KPIs del día, ganancia estimada y desglose por método de pago
GET /api/reportes/top-productos/?periodo=hoy|semana|mes   top 5 por unidades y por ganancia
GET /api/reportes/tendencia/?dias=7|30     ingresos vs. costos por día
"""
from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.faltantes.models import Faltante
from apps.usuarios.permissions import EsAdministrador
from config.filtros import leer_fecha, rango_fechas

from . import consultas


def rango_o_hoy(request):
    desde, hasta = rango_fechas(request)
    hoy = timezone.localdate()
    desde = desde or hasta or hoy
    hasta = hasta or desde
    if desde > hasta:
        raise ValidationError({"desde": "La fecha inicial no puede ser posterior a la final."})
    return desde, hasta


def leer_limite(request, por_defecto=10):
    texto = request.query_params.get("limite")
    if not texto:
        return por_defecto
    if not texto.isdigit() or not 1 <= int(texto) <= 100:
        raise ValidationError({"limite": "El límite debe ser un número entre 1 y 100."})
    return int(texto)


class ReporteBase(APIView):
    permission_classes = [IsAuthenticated, EsAdministrador]


class ReporteVentasView(ReporteBase):
    def get(self, request):
        return Response(consultas.reporte_ventas(*rango_o_hoy(request)))


class ReporteProductosMasVendidosView(ReporteBase):
    def get(self, request):
        desde, hasta = rango_o_hoy(request)
        return Response(consultas.reporte_productos_mas_vendidos(desde, hasta, leer_limite(request)))


class ReporteComprasView(ReporteBase):
    def get(self, request):
        return Response(consultas.reporte_compras(*rango_o_hoy(request)))


class ReporteFaltantesFrecuentesView(ReporteBase):
    def get(self, request):
        desde, hasta = rango_fechas(request)
        if bool(desde) != bool(hasta):
            desde = hasta = desde or hasta
        estado = request.query_params.get("estado")
        if estado and estado not in Faltante.Estado.values:
            raise ValidationError({"estado": "Usa estado=pendiente o estado=resuelto."})
        return Response(
            consultas.reporte_faltantes_frecuentes(desde, hasta, estado, leer_limite(request))
        )


class ResumenDiaView(ReporteBase):
    def get(self, request):
        fecha = leer_fecha(request, "fecha") or timezone.localdate()
        return Response(consultas.resumen_dia(fecha))


def rango_de_periodo(request):
    """hoy | semana (desde el lunes) | mes (desde el día 1). También acepta desde/hasta."""
    desde, hasta = rango_fechas(request)
    if desde or hasta:
        return desde or hasta, hasta or desde
    hoy = timezone.localdate()
    periodo = request.query_params.get("periodo", "hoy")
    if periodo == "hoy":
        return hoy, hoy
    if periodo == "semana":
        return hoy - timedelta(days=hoy.weekday()), hoy
    if periodo == "mes":
        return hoy.replace(day=1), hoy
    raise ValidationError({"periodo": "Usa periodo=hoy, semana o mes."})


class TopProductosView(ReporteBase):
    def get(self, request):
        desde, hasta = rango_de_periodo(request)
        limite = leer_limite(request, por_defecto=5)
        return Response(consultas.top_productos(desde, hasta, limite))


class TendenciaView(ReporteBase):
    def get(self, request):
        texto = request.query_params.get("dias", "7")
        if texto not in {"7", "30"}:
            raise ValidationError({"dias": "Usa dias=7 o dias=30."})
        return Response(consultas.tendencia(timezone.localdate(), int(texto)))
