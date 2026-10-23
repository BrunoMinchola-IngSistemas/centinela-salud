from rest_framework.routers import DefaultRouter

from .views import AssetViewSet, DiscoveryRunViewSet

router = DefaultRouter()
router.register("assets", AssetViewSet, basename="asset")
router.register("descubrimientos", DiscoveryRunViewSet, basename="descubrimiento")

urlpatterns = router.urls
