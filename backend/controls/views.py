from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from common.mixins import OrganizationScopedMixin
from integrations.qwen import suggest_control_improvement

from .models import Control
from .serializers import ControlSerializer


class ControlViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Control.objects.prefetch_related("mappings", "vulnerabilities", "assessments").all()
    serializer_class = ControlSerializer

    @action(detail=True, methods=["post"])
    def assess(self, request, pk=None):
        """
        Dispara una evaluación con IA: le pasa a Qwen el control y sus
        hallazgos asociados y guarda la recomendación como un nuevo
        ComplianceAssessment. Qwen corre en la red local de la clínica;
        este endpoint solo orquesta la llamada.
        """
        control = self.get_object()
        assessment = suggest_control_improvement(control)
        return Response(
            {
                "control": control.id,
                "score": assessment.score,
                "recommendation": assessment.recommendation,
            }
        )
