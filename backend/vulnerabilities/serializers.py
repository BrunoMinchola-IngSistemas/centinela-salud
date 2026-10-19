from rest_framework import serializers

from assets.serializers import AssetSerializer

from .models import Vulnerability, VulnerabilitySource


class VulnerabilitySourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = VulnerabilitySource
        fields = ["id", "source_type", "name", "is_active", "last_sync_at", "last_sync_ok"]


class VulnerabilityListSerializer(serializers.ModelSerializer):
    """Versión liviana para la tabla principal (sin descripción larga ni pasos de IA)."""

    asset_hostname = serializers.CharField(source="asset.hostname", read_only=True)
    source_name = serializers.CharField(source="source.get_source_type_display", read_only=True)
    is_overdue = serializers.ReadOnlyField()

    class Meta:
        model = Vulnerability
        fields = [
            "id",
            "cve",
            "title",
            "severity",
            "cvss_score",
            "epss_score",
            "priority_score",
            "status",
            "due_date",
            "is_overdue",
            "asset",
            "asset_hostname",
            "source",
            "source_name",
        ]


class VulnerabilityDetailSerializer(VulnerabilityListSerializer):
    """Versión completa para el panel de análisis de IA."""

    asset = AssetSerializer(read_only=True)
    control_ids = serializers.PrimaryKeyRelatedField(source="controls", many=True, read_only=True)

    class Meta(VulnerabilityListSerializer.Meta):
        fields = VulnerabilityListSerializer.Meta.fields + [
            "description",
            "ai_summary",
            "ai_remediation_steps",
            "ai_rollback_risk",
            "ai_analyzed_at",
            "control_ids",
            "first_detected_at",
            "last_seen_at",
            "closed_at",
        ]
