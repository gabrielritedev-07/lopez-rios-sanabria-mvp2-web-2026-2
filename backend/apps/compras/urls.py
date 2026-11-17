from rest_framework.routers import SimpleRouter

from .views import CompraViewSet

router = SimpleRouter()
router.register("compras", CompraViewSet, basename="compra")

urlpatterns = router.urls
