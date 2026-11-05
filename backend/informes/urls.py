from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ReporteViewSet, ResumenEjecutivoView

router = DefaultRouter()
router.register("reportes", ReporteViewSet, basename="reporte")

urlpatterns = [
    path("ejecutivo/resumen/", ResumenEjecutivoView.as_view(), name="ejecutivo-resumen"),
] + router.urls
