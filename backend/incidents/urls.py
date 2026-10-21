from rest_framework.routers import DefaultRouter

from .views import IncidenteReportadoViewSet

router = DefaultRouter()
router.register("incidentes", IncidenteReportadoViewSet, basename="incidente")

urlpatterns = router.urls
