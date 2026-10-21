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
    # El catálogo completo (~31 controles) cabe en una sola página y la
    # vista de cumplimiento por tema necesita verlos todos juntos.
    pagination_class = None

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


def _por_tema(controles):
    """HU13: % de cumplimiento promedio por tema del Anexo A."""
    from collections import defaultdict

    acum = defaultdict(list)
    for c in controles:
        acum[c["theme_display"] or "Sin tema"].append(c["compliance_score"])
    return [
        {"tema": tema, "controles": len(v), "cumplimiento": round(sum(v) / len(v))}
        for tema, v in sorted(acum.items())
    ]


@action(detail=False, methods=["get"], url_path="por-tema")
def por_tema(self, request):
    data = ControlSerializer(self.get_queryset(), many=True).data
    return Response(_por_tema(data))


ControlViewSet.por_tema = por_tema
