from rest_framework.routers import DefaultRouter

from .views import AccionAgenteViewSet, PoliticaAutonomiaViewSet, RegistroAuditoriaViewSet, SolicitudAprobacionViewSet

router = DefaultRouter()
router.register("politicas-autonomia", PoliticaAutonomiaViewSet, basename="politica-autonomia")
router.register("solicitudes-aprobacion", SolicitudAprobacionViewSet, basename="solicitud-aprobacion")
router.register("registros-auditoria", RegistroAuditoriaViewSet, basename="registro-auditoria")
router.register("acciones-agente", AccionAgenteViewSet, basename="accion-agente")

urlpatterns = router.urls
