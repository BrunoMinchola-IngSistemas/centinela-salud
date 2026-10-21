from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from common.mixins import OrganizationScopedMixin
from governance.audit import registrar
from governance.models import NivelAutonomia

from .models import IncidenteReportado
from .serializers import IncidenteReportadoSerializer


class IncidenteReportadoViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """HU30: reportar un incidente con 3 campos (qué, dónde, cuándo)."""

    serializer_class = IncidenteReportadoSerializer
    permission_classes = [IsAuthenticated]
    queryset = IncidenteReportado.objects.all()

    def perform_create(self, serializer):
        incidente = serializer.save(organization=self._organization(), reportado_por=self.request.user.username)
        registrar(
            organization=self._organization(),
            actor=self.request.user.username,
            accion="incidente_reportado",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="incidente",
            objeto_id=incidente.id,
            detalle={"lugar": incidente.lugar},
        )
