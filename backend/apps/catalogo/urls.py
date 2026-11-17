from rest_framework.routers import SimpleRouter

from .views import (
    CategoriaViewSet,
    ClienteViewSet,
    DescuentoViewSet,
    ProductoViewSet,
    ProveedorViewSet,
)

router = SimpleRouter()
router.register("categorias", CategoriaViewSet, basename="categoria")
router.register("clientes", ClienteViewSet, basename="cliente")
router.register("proveedores", ProveedorViewSet, basename="proveedor")
router.register("productos", ProductoViewSet, basename="producto")
router.register("descuentos", DescuentoViewSet, basename="descuento")

urlpatterns = router.urls
