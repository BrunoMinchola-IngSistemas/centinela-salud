from rest_framework.routers import DefaultRouter

from .views import CatalogoCVEViewSet, VulnerabilitySourceViewSet, VulnerabilityViewSet

router = DefaultRouter()
router.register("vulnerabilities", VulnerabilityViewSet, basename="vulnerability")
router.register("sources", VulnerabilitySourceViewSet, basename="source")
router.register("cve", CatalogoCVEViewSet, basename="cve")

urlpatterns = router.urls
