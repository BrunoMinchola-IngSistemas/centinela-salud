from rest_framework import viewsets

from common.mixins import OrganizationScopedMixin

from .models import Evidence
from .serializers import EvidenceSerializer


class EvidenceViewSet(OrganizationScopedMixin, viewsets.ReadOnlyModelViewSet):
    """
    Solo lectura: las evidencias se generan desde el flujo de
    verificación (remediation.views.RemediationPlanViewSet.verify) o
    por una futura carga manual, nunca editándolas a mano aquí, para
    no romper la trazabilidad de auditoría.
    """

    queryset = Evidence.objects.select_related("vulnerability", "plan")
    serializer_class = EvidenceSerializer
    filterset_fields = ["evidence_type", "source_system"]
