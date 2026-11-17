from django.urls import path

from .views import (
    ResumenDiaView,
    TendenciaView,
    TopProductosView,
    ReporteComprasView,
    ReporteFaltantesFrecuentesView,
    ReporteProductosMasVendidosView,
    ReporteVentasView,
)

urlpatterns = [
    path("ventas/", ReporteVentasView.as_view(), name="reporte-ventas"),
    path(
        "productos-mas-vendidos/",
        ReporteProductosMasVendidosView.as_view(),
        name="reporte-productos-mas-vendidos",
    ),
    path("compras/", ReporteComprasView.as_view(), name="reporte-compras"),
    path(
        "faltantes-frecuentes/",
        ReporteFaltantesFrecuentesView.as_view(),
        name="reporte-faltantes-frecuentes",
    ),
    path("resumen-dia/", ResumenDiaView.as_view(), name="reporte-resumen-dia"),
    path("top-productos/", TopProductosView.as_view(), name="reporte-top-productos"),
    path("tendencia/", TendenciaView.as_view(), name="reporte-tendencia"),
]
