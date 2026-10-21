from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.mixins import OrganizationScopedMixin

from .audit import registrar
from .models import EstadoSolicitud, NivelAutonomia, PoliticaAutonomia, RegistroAuditoria, SolicitudAprobacion
from .serializers import (
    PoliticaAutonomiaSerializer,
    RegistroAuditoriaSerializer,
    SolicitudAprobacionSerializer,
)


class PoliticaAutonomiaViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """HU23: qué nivel de autonomía aplica a cada tipo de acción, por organización."""

    serializer_class = PoliticaAutonomiaSerializer
    permission_classes = [IsAuthenticated]
    queryset = PoliticaAutonomia.objects.all()


class SolicitudAprobacionViewSet(viewsets.ModelViewSet):
    """
    HU24: solicitudes de aprobación para acciones de alto impacto.

    No usa OrganizationScopedMixin porque SolicitudAprobacion no tiene
    un FK directo a Organization (llega a ella vía
    plan -> vulnerability -> organization), así que el filtro y la
    creación se escriben a mano abajo. Decidir (aprobar/rechazar) se
    hace con las acciones dedicadas, no con un PATCH libre, para dejar
    registrado quién decidió y por qué.
    """

    serializer_class = SolicitudAprobacionSerializer
    permission_classes = [IsAuthenticated]
    queryset = SolicitudAprobacion.objects.select_related("plan__vulnerability__organization")

    def _organization(self):
        profile = getattr(self.request.user, "profile", None)
        if profile is None:
            raise PermissionDenied("El usuario no tiene un perfil de organización asociado.")
        return profile.organization

    def get_queryset(self):
        return super().get_queryset().filter(plan__vulnerability__organization=self._organization())

    def perform_create(self, serializer):
        solicitud = serializer.save()
        registrar(
            organization=self._organization(),
            actor=self.request.user.username,
            accion="solicitud_creada",
            modalidad=NivelAutonomia.CON_APROBACION,
            objeto_tipo="remediation_plan",
            objeto_id=solicitud.plan_id,
            detalle={"solicitud_id": str(solicitud.id), "tipo_accion": solicitud.tipo_accion},
        )

    def _decidir(self, request, estado, accion_log):
        solicitud = self.get_object()
        solicitud.estado = estado
        solicitud.decidido_por = request.user.username
        solicitud.decidido_en = timezone.now()
        solicitud.comentario_decision = request.data.get("comentario", "")
        solicitud.save(update_fields=["estado", "decidido_por", "decidido_en", "comentario_decision"])

        registrar(
            organization=self._organization(),
            actor=request.user.username,
            accion=accion_log,
            modalidad=NivelAutonomia.CON_APROBACION,
            objeto_tipo="remediation_plan",
            objeto_id=solicitud.plan_id,
            detalle={"solicitud_id": str(solicitud.id), "comentario": solicitud.comentario_decision},
        )
        return solicitud

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        solicitud = self._decidir(request, EstadoSolicitud.APROBADA, "solicitud_aprobada")
        return Response(SolicitudAprobacionSerializer(solicitud).data)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        solicitud = self._decidir(request, EstadoSolicitud.RECHAZADA, "solicitud_rechazada")
        return Response(SolicitudAprobacionSerializer(solicitud).data)


class RegistroAuditoriaViewSet(
    OrganizationScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    HU27 / RNF-05: "log no editable ni borrable". A propósito NO hereda
    de ModelViewSet: solo expone list/retrieve/create (vía los mixins
    de arriba), así que no existe ninguna ruta DRF para update,
    partial_update ni destroy, sin importar qué intente mandar el
    cliente.
    """

    serializer_class = RegistroAuditoriaSerializer
    permission_classes = [IsAuthenticated]
    queryset = RegistroAuditoria.objects.all()
