from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from common.mixins import OrganizationScopedMixin
from integrations import qwen
from integrations.sync import sync_all_sources
from governance.audit import registrar
from governance.models import NivelAutonomia

from .models import Vulnerability, VulnerabilitySource
from .serializers import (
    VulnerabilityDetailSerializer,
    VulnerabilityListSerializer,
    VulnerabilitySourceSerializer,
)


class VulnerabilityViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Vulnerability.objects.select_related("asset", "source").prefetch_related("controls")
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["severity", "status", "source__source_type", "asset"]
    search_fields = ["cve", "title", "asset__hostname"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VulnerabilityDetailSerializer
        return VulnerabilityListSerializer

    def get_queryset(self):
        return super().get_queryset().order_by("-priority_score")

    @action(detail=True, methods=["post"])
    def analyze(self, request, pk=None):
        """
        Pide a Qwen (local) el resumen de riesgo y los pasos de
        corrección para este hallazgo, y los guarda en el propio
        registro para no tener que volver a pedirlos cada vez que se
        abre el panel de IA.
        """
        vulnerability = self.get_object()
        analysis = qwen.analyze_vulnerability(vulnerability)
        vulnerability.ai_summary = analysis.summary
        vulnerability.ai_remediation_steps = analysis.steps
        vulnerability.ai_rollback_risk = analysis.rollback_risk
        vulnerability.priority_score = analysis.priority_score
        vulnerability.ai_analyzed_at = timezone.now()
        vulnerability.save(
            update_fields=[
                "ai_summary",
                "ai_remediation_steps",
                "ai_rollback_risk",
                "priority_score",
                "ai_analyzed_at",
            ]
        )
        registrar(
            organization=vulnerability.organization,
            actor="agente",
            accion="analisis_ia",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="vulnerability",
            objeto_id=vulnerability.id,
            detalle={"pedido_por": request.user.username, "hallazgo": vulnerability.title},
        )
        return Response(VulnerabilityDetailSerializer(vulnerability).data)

    @action(detail=True, methods=["post"])
    def explain_simple(self, request, pk=None):
        vulnerability = self.get_object()
        return Response({"text": qwen.simplify_explanation(vulnerability)})

    @action(detail=True, methods=["post"])
    def clinical_impact(self, request, pk=None):
        vulnerability = self.get_object()
        return Response({"text": qwen.clinical_impact(vulnerability)})


class VulnerabilitySourceViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = VulnerabilitySource.objects.all()
    serializer_class = VulnerabilitySourceSerializer

    @action(detail=False, methods=["post"])
    def sync(self, request):
        """Botón 'Sincronizar' de la consola: recorre todas las fuentes activas de la organización."""
        results = sync_all_sources(self._organization())
        return Response({"results": results})
