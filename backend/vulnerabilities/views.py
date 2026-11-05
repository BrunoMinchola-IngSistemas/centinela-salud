import django_filters
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from accounts.models import Role
from common.mixins import OrganizationScopedMixin
from common.modulos import MODULOS, puede
from common.permissions import exigir_rol
from governance.audit import registrar
from governance.models import NivelAutonomia
from informes.exportar import exportar_tabla
from integrations import qwen
from integrations.sync import sync_all_sources

from . import ml
from .analitica import matriz_riesgos, tendencia
from .models import CatalogoCVE, EntrenamientoModelo, SincronizacionCVE, Vulnerability, VulnerabilitySource
from .serializers import (
    CatalogoCVESerializer,
    CorregirClasificacionSerializer,
    EntrenamientoSerializer,
    SincronizacionCVESerializer,
    VulnerabilityDetailSerializer,
    VulnerabilityListSerializer,
    VulnerabilitySourceSerializer,
)

ROLES_CORRIGEN = {Role.ADMIN, Role.IT_OWNER, Role.ANALYST}
ETIQUETA = {"critical": "Crítica", "high": "Alta", "medium": "Media", "low": "Baja", "none": "Ninguna", "": "Pendiente"}


class VulnerabilityFilter(django_filters.FilterSet):
    """HU10: historial filtrable por fecha, severidad y activo."""

    detectado_desde = django_filters.DateFilter(field_name="first_detected_at", lookup_expr="date__gte")
    detectado_hasta = django_filters.DateFilter(field_name="first_detected_at", lookup_expr="date__lte")
    pendiente_asociacion = django_filters.BooleanFilter(field_name="asset", lookup_expr="isnull")

    class Meta:
        model = Vulnerability
        fields = ["severity", "status", "source__source_type", "asset", "contextual_priority", "category"]


class VulnerabilityViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Vulnerability.objects.select_related("asset", "source", "plan").prefetch_related("controls")
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = VulnerabilityFilter
    search_fields = ["cve", "title", "asset__hostname"]
    modulo = "vulnerabilidades"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return VulnerabilityDetailSerializer
        return VulnerabilityListSerializer

    def get_queryset(self):
        return super().get_queryset().order_by("-priority_score", "-first_detected_at")

    def perform_create(self, serializer):
        vuln = serializer.save(organization=self._organization())
        registrar(
            organization=vuln.organization,
            actor=self.request.user.username,
            accion="hallazgo_registrado",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="vulnerability",
            objeto_id=vuln.id,
            detalle={"titulo": vuln.title, "cvss": str(vuln.cvss_score), "pendiente_asociacion": vuln.asset_id is None},
        )

    def perform_update(self, serializer):
        antes = serializer.instance.cvss_score
        vuln = serializer.save()
        if vuln.cvss_score != antes:
            registrar(
                organization=vuln.organization,
                actor=self.request.user.username,
                accion="cvss_recalculado",
                modalidad=NivelAutonomia.ASISTIDO,
                objeto_tipo="vulnerability",
                objeto_id=vuln.id,
                detalle={"de": str(antes), "a": str(vuln.cvss_score), "vector": vuln.cvss_vector},
            )

    # ------------------------------------------------------------- IA (Qwen)

    @action(detail=True, methods=["post"])
    def analyze(self, request, pk=None):
        """
        Pide a Qwen el resumen de riesgo y los pasos de corrección para
        este hallazgo, y los guarda en el propio registro para no tener
        que volver a pedirlos cada vez que se abre el panel de IA.
        """
        vulnerability = self.get_object()
        analysis = qwen.analyze_vulnerability(vulnerability)
        vulnerability.ai_summary = analysis.summary
        vulnerability.ai_remediation_steps = analysis.steps
        vulnerability.ai_rollback_risk = analysis.rollback_risk
        vulnerability.priority_score = analysis.priority_score
        vulnerability.ai_analyzed_at = timezone.now()
        vulnerability.save(
            update_fields=["ai_summary", "ai_remediation_steps", "ai_rollback_risk", "priority_score", "ai_analyzed_at"]
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
        return Response(VulnerabilityDetailSerializer(vulnerability, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def explain_simple(self, request, pk=None):
        vulnerability = self.get_object()
        return Response({"text": qwen.simplify_explanation(vulnerability)})

    @action(detail=True, methods=["post"])
    def clinical_impact(self, request, pk=None):
        vulnerability = self.get_object()
        return Response({"text": qwen.clinical_impact(vulnerability)})

    # ------------------------------------------------------------- HU08 (SVM)

    @action(detail=True, methods=["post"])
    def clasificar(self, request, pk=None):
        vuln = self.get_object()
        nivel, registro = ml.clasificar(vuln)
        if nivel is None:
            return Response(
                {"detail": "El hallazgo no tiene activo asociado: no hay contexto para clasificarlo (pendiente de asociación)."},
                status=400,
            )
        registrar(
            organization=vuln.organization,
            actor="agente",
            accion="clasificacion_sugerida",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="vulnerability",
            objeto_id=vuln.id,
            detalle={"sugerido": nivel, "accuracy": registro.accuracy, "f1_macro": registro.f1_macro},
        )
        return Response(
            {"riesgo_sugerido": nivel, "riesgo_sugerido_display": ETIQUETA[nivel], "modelo": EntrenamientoSerializer(registro).data}
        )

    @action(detail=True, methods=["post"], url_path="corregir-clasificacion")
    def corregir_clasificacion(self, request, pk=None):
        exigir_rol(request, ROLES_CORRIGEN, "Solo TI, el Analista o la Gerencia pueden corregir una clasificación.")
        vuln = self.get_object()
        datos = CorregirClasificacionSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        anterior = vuln.riesgo_corregido or vuln.riesgo_sugerido
        vuln.riesgo_corregido = datos.validated_data["riesgo"]
        vuln.motivo_correccion = datos.validated_data["motivo"]
        vuln.riesgo_corregido_por = request.user.username
        vuln.riesgo_corregido_en = timezone.now()
        vuln.save(update_fields=["riesgo_corregido", "motivo_correccion", "riesgo_corregido_por", "riesgo_corregido_en"])
        registrar(
            organization=vuln.organization,
            actor=request.user.username,
            accion="clasificacion_corregida",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="vulnerability",
            objeto_id=vuln.id,
            detalle={"sugerido": vuln.riesgo_sugerido, "anterior": anterior, "corregido": vuln.riesgo_corregido, "motivo": vuln.motivo_correccion},
        )
        return Response(VulnerabilityDetailSerializer(vuln, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get", "post"])
    def modelo(self, request):
        """GET: último entrenamiento (métricas). POST: reentrenar y clasificar los hallazgos abiertos."""
        org = self._organization()
        if request.method == "POST":
            exigir_rol(request, ROLES_CORRIGEN, "Solo TI, el Analista o la Gerencia pueden reentrenar el modelo.")
            _, registro = ml.entrenar(org, forzar=True)
            clasificados = 0
            for v in self.get_queryset().exclude(status="closed").filter(asset__isnull=False):
                ml.clasificar(v)
                clasificados += 1
            return Response({"modelo": EntrenamientoSerializer(registro).data, "clasificados": clasificados})
        registro = EntrenamientoModelo.objects.filter(organization=org).first()
        if registro is None:
            _, registro = ml.entrenar(org)
        return Response({"modelo": EntrenamientoSerializer(registro).data})

    # ------------------------------------------------------------- HU09 / HU10

    @action(detail=False, methods=["get"], url_path="matriz-riesgos")
    def matriz_riesgos(self, request):
        profile = request.user.profile
        if not puede(profile.role, "riesgos"):
            raise PermissionDenied(f"Permisos insuficientes: tu rol no tiene acceso al módulo «{MODULOS['riesgos']}».")
        qs = self.filter_queryset(self.get_queryset())
        nivel = request.query_params.get("nivel") or None
        return Response(matriz_riesgos(qs, nivel=nivel))

    @action(detail=False, methods=["get"])
    def tendencia(self, request):
        qs = self.filter_queryset(self.get_queryset())
        try:
            meses = max(3, min(24, int(request.query_params.get("meses", 6))))
        except ValueError:
            meses = 6
        return Response(tendencia(qs, meses=meses))

    @action(detail=False, methods=["get"])
    def exportar(self, request):
        """Historial filtrado a CSV / Excel / PDF (HU10)."""
        qs = self.filter_queryset(self.get_queryset())
        columnas = ["CVE", "Hallazgo", "Activo", "Severidad", "CVSS", "Prioridad", "Estado", "Detectado", "Cerrado"]
        filas = [
            [v.cve or "-", v.title, v.asset.hostname if v.asset else "Pendiente de asociación", v.get_severity_display(),
             str(v.cvss_score or "-"), ETIQUETA.get(v.contextual_priority, v.contextual_priority), v.get_status_display(),
             timezone.localtime(v.first_detected_at).strftime("%d/%m/%Y"),
             timezone.localtime(v.closed_at).strftime("%d/%m/%Y") if v.closed_at else ""]
            for v in qs
        ]
        return exportar_tabla(
            "historial_vulnerabilidades", "Historial de vulnerabilidades", columnas, filas,
            request.query_params.get("formato", "csv"), anchos=(14, 40, 18, 10, 7, 10, 12, 11, 11),
        )


class VulnerabilitySourceViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = VulnerabilitySource.objects.all()
    serializer_class = VulnerabilitySourceSerializer
    modulo = "integraciones"

    @action(detail=False, methods=["post"])
    def sync(self, request):
        """Botón 'Sincronizar' de la consola: recorre todas las fuentes activas de la organización."""
        results = sync_all_sources(self._organization())
        return Response({"results": results})


class CatalogoCVEViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """HU03: base de conocimiento de CVE (pública, común a todas las clínicas)."""

    serializer_class = CatalogoCVESerializer
    queryset = CatalogoCVE.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["kev", "severidad"]
    search_fields = ["cve_id", "descripcion"]
    lookup_field = "cve_id"
    lookup_value_regex = r"CVE-\d{4}-\d+"
    modulo = "integraciones"

    @action(detail=False, methods=["get"])
    def sincronizaciones(self, request):
        ultimas = SincronizacionCVE.objects.all()[:20]
        ultima_ok = SincronizacionCVE.objects.filter(ok=True).first()
        return Response(
            {
                "total_cve": CatalogoCVE.objects.count(),
                "total_kev": CatalogoCVE.objects.filter(kev=True).count(),
                "ultima_ok": SincronizacionCVESerializer(ultima_ok).data if ultima_ok else None,
                "historial": SincronizacionCVESerializer(ultimas, many=True).data,
            }
        )

    @action(detail=False, methods=["post"])
    def sincronizar(self, request):
        exigir_rol(request, {Role.ADMIN, Role.IT_OWNER}, "Solo la Gerencia o TI pueden lanzar la sincronización de CVE.")
        from .cve_feed import sincronizar

        sync = sincronizar(horas=int(request.data.get("horas", 24) or 24))
        return Response(SincronizacionCVESerializer(sync).data, status=201 if sync.ok else 502)
