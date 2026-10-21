from rest_framework.routers import DefaultRouter

from .views import PoliticaAutonomiaViewSet, RegistroAuditoriaViewSet, SolicitudAprobacionViewSet

router = DefaultRouter()
router.register("politicas-autonomia", PoliticaAutonomiaViewSet, basename="politica-autonomia")
router.register("solicitudes-aprobacion", SolicitudAprobacionViewSet, basename="solicitud-aprobacion")
router.register("registros-auditoria", RegistroAuditoriaViewSet, basename="registro-auditoria")

urlpatterns = router.urls
