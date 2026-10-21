from rest_framework import serializers

from vulnerabilities.models import VulnerabilityStatus

from .models import ComplianceAssessment, Control, ControlMapping


class ControlMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlMapping
        fields = ["framework", "code"]


class ComplianceAssessmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceAssessment
        fields = ["id", "score", "generated_by_ai", "recommendation", "created_at", "created_by"]
        read_only_fields = ["id", "created_at"]


class ControlSerializer(serializers.ModelSerializer):
    """
    Expone, además de los datos propios del control, un cumplimiento
    calculado a partir de las vulnerabilidades abiertas/cerradas que
    tiene asociadas (igual que hace el mockup de la consola).
    """

    mappings = ControlMappingSerializer(many=True, read_only=True)
    theme_display = serializers.CharField(source="get_theme_display", read_only=True)
    compliance_score = serializers.SerializerMethodField()
    open_findings = serializers.SerializerMethodField()
    latest_assessment = serializers.SerializerMethodField()

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
            "mappings",
            "compliance_score",
            "open_findings",
            "latest_assessment",
        ]

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
