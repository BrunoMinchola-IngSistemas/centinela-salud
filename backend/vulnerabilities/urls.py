from rest_framework.routers import DefaultRouter

from .views import VulnerabilitySourceViewSet, VulnerabilityViewSet

router = DefaultRouter()
router.register("vulnerabilities", VulnerabilityViewSet, basename="vulnerability")
router.register("sources", VulnerabilitySourceViewSet, basename="source")

urlpatterns = router.urls
