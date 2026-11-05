from rest_framework import serializers

from vulnerabilities.models import VulnerabilityStatus

from .models import ComplianceAssessment, Control, ControlMapping
from .services import es_brecha_pendiente, tiene_evidencia


class ControlMappingSerializer(serializers.ModelSerializer):
    framework_display = serializers.CharField(source="get_framework_display", read_only=True)

    class Meta:
        model = ControlMapping
        fields = ["framework", "framework_display", "code"]


class ComplianceAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceAssessment
        fields = ["id", "score", "generated_by_ai", "recommendation", "created_at", "created_by"]
        read_only_fields = ["id", "created_at"]


class ControlSerializer(serializers.ModelSerializer):
    """
    Datos del control + estado de implementación (lo único editable,
    HU13) + indicadores calculados: puntaje técnico por hallazgos
    abiertos/cerrados, si tiene evidencia y si es una brecha pendiente
    (HU11 esc. 2).
    """

    mappings = ControlMappingSerializer(many=True, read_only=True)
    theme_display = serializers.CharField(source="get_theme_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_implementacion_display", read_only=True)
    compliance_score = serializers.SerializerMethodField()
    open_findings = serializers.SerializerMethodField()
    latest_assessment = serializers.SerializerMethodField()
    tiene_evidencia = serializers.SerializerMethodField()
    brecha_pendiente = serializers.SerializerMethodField()

    class Meta:
        model = Control
        fields = [
            "id",
            "iso_code",
            "theme",
            "theme_display",
            "name",
            "description",
            "health_rationale",
            "baseline_score",
            "estado_implementacion",
            "estado_display",
            "estado_actualizado_en",
            "estado_actualizado_por",
            "madurez_minima",
            "criticidad",
            "costo_estimado",
            "mappings",
            "compliance_score",
            "open_findings",
            "latest_assessment",
            "tiene_evidencia",
            "brecha_pendiente",
        ]
        read_only_fields = [f for f in fields if f != "estado_implementacion"]

    def get_compliance_score(self, obj):
        linked = obj.vulnerabilities.all()
        open_count = linked.exclude(status=VulnerabilityStatus.CLOSED).count()
        closed_count = linked.filter(status=VulnerabilityStatus.CLOSED).count()
        score = obj.baseline_score - open_count * 3 + closed_count * 3
        return max(20, min(99, score))

    def get_open_findings(self, obj):
        return obj.vulnerabilities.exclude(status=VulnerabilityStatus.CLOSED).count()

    def get_latest_assessment(self, obj):
        last = obj.assessments.first()
        return ComplianceAssessmentSerializer(last).data if last else None

    def get_tiene_evidencia(self, obj):
        return tiene_evidencia(obj)

    def get_brecha_pendiente(self, obj):
        return es_brecha_pendiente(obj)
