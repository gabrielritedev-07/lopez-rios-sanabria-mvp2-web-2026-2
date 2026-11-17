from rest_framework.routers import SimpleRouter

from .views import FaltanteViewSet

router = SimpleRouter()
router.register("faltantes", FaltanteViewSet, basename="faltante")

urlpatterns = router.urls
