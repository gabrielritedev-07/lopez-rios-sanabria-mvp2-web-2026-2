from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AbonoClienteView, CarteraClienteView, VentaViewSet

router = SimpleRouter()
router.register("ventas", VentaViewSet, basename="venta")

urlpatterns = router.urls + [
    path("clientes/<int:pk>/cartera/", CarteraClienteView.as_view(), name="cliente-cartera"),
    path("clientes/<int:pk>/abonos/", AbonoClienteView.as_view(), name="cliente-abonos"),
]
