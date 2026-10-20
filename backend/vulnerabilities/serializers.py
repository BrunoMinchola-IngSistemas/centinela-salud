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

    def validate_cvss_score(self, value):
        """
        El modelo no tiene validadores de rango (DecimalField solo
        obliga la cantidad de dígitos), así que un POST/PATCH podía
        guardar un CVSS como 50 o -3 sin que nada lo impidiera. La
        escala CVSS va de 0.0 a 10.0.
        """
        if value is not None and not (0 <= value <= 10):
            raise serializers.ValidationError("El puntaje CVSS debe estar entre 0.0 y 10.0.")
        return value

    def validate_epss_score(self, value):
        """EPSS es una probabilidad (0-1), no una escala CVSS."""
        if value is not None and not (0 <= value <= 1):
            raise serializers.ValidationError("El puntaje EPSS debe estar entre 0.0 y 1.0.")
        return value


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
