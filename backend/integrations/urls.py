from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AsistenteView, EstadoIntegracionesView, FallaIntegracionViewSet, RegistroIncompletoViewSet

router = DefaultRouter()
router.register("integraciones/fallas", FallaIntegracionViewSet, basename="falla-integracion")
router.register("registros-incompletos", RegistroIncompletoViewSet, basename="registro-incompleto")

urlpatterns = [
    path("integraciones/estado/", EstadoIntegracionesView.as_view(), name="integraciones-estado"),
    path("asistente/preguntar/", AsistenteView.as_view(), name="asistente-preguntar"),
] + router.urls
