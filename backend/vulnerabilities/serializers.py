from rest_framework import serializers

from assets.serializers import AssetSerializer
from common.privacidad import seudonimizar_texto
from common.serializers import OrganizationScopedRelationsMixin

from .cvss import validar_vector
from .models import CatalogoCVE, EntrenamientoModelo, SincronizacionCVE, Vulnerability, VulnerabilitySource

NIVELES_RIESGO = ["low", "medium", "high", "critical"]


class VulnerabilitySourceSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)

    class Meta:
        model = VulnerabilitySource
        fields = ["id", "source_type", "source_type_display", "name", "is_active", "last_sync_at", "last_sync_ok"]


class VulnerabilityListSerializer(OrganizationScopedRelationsMixin, serializers.ModelSerializer):
    """Versión liviana para la tabla principal (sin descripción larga ni pasos de IA)."""

    asset_hostname = serializers.CharField(source="asset.hostname", read_only=True, default="")
    source_name = serializers.CharField(source="source.get_source_type_display", read_only=True)
    is_overdue = serializers.ReadOnlyField()
    fecha_limite = serializers.DateField(read_only=True)
    contextual_priority = serializers.CharField(read_only=True)
    priority_rules = serializers.JSONField(read_only=True)
    nivel_impacto = serializers.CharField(read_only=True)
    pendiente_asociacion = serializers.BooleanField(read_only=True)
    riesgo_final = serializers.CharField(read_only=True)

    class Meta:
        model = Vulnerability
        fields = [
            "id",
            "external_id",
            "cve",
            "title",
            "severity",
            "cvss_score",
            "cvss_vector",
            "epss_score",
            "priority_score",
            "category",
            "actively_exploited",
            "contextual_priority",
            "priority_rules",
            "nivel_impacto",
            "pendiente_asociacion",
            "riesgo_sugerido",
            "riesgo_corregido",
            "riesgo_final",
            "status",
            "due_date",
            "fecha_limite",
            "is_overdue",
            "asset",
            "asset_hostname",
            "source",
            "source_name",
            "first_detected_at",
            "closed_at",
        ]
        read_only_fields = ["riesgo_sugerido", "riesgo_corregido", "first_detected_at", "closed_at"]
        extra_kwargs = {"asset": {"required": False, "allow_null": True}, "severity": {"required": False}}

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

    def validate_cvss_vector(self, value):
        error = validar_vector(value)
        if error:
            raise serializers.ValidationError(error)
        return (value or "").strip()

    def validate_description(self, value):
        return seudonimizar_texto(value)

    def validate(self, data):
        if self.instance is None and not data.get("severity") and not data.get("cvss_vector"):
            raise serializers.ValidationError({"severity": "Indica la severidad o el vector CVSS."})
        return data


class VulnerabilityDetailSerializer(VulnerabilityListSerializer):
    """Versión completa para el panel de detalle (explicación, IA, ML, activos relacionados)."""

    asset = AssetSerializer(read_only=True)
    control_ids = serializers.PrimaryKeyRelatedField(source="controls", many=True, read_only=True)
    control_codes = serializers.SerializerMethodField()
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    explicacion = serializers.SerializerMethodField()
    activos_relacionados = serializers.SerializerMethodField()
    catalogo_cve = serializers.SerializerMethodField()

    def get_control_codes(self, obj):
        codes = [c.iso_code for c in obj.controls.all() if c.iso_code]
        return sorted(codes, key=lambda x: tuple(int(p) for p in x.split(".")))

    def get_explicacion(self, obj):
        from .analitica import explicacion

        return explicacion(obj)

    def get_activos_relacionados(self, obj):
        """HU07: el activo afectado y los demás de la clínica con la misma CVE abierta."""
        from assets.models import Asset

        filas = []
        if obj.asset:
            filas.append(obj.asset)
        if obj.cve:
            otros = Asset.objects.filter(
                organization=obj.organization, vulnerabilities__cve=obj.cve
            ).exclude(vulnerabilities__status="closed").exclude(id=obj.asset_id).distinct()
            filas += list(otros)
        return [
            {
                "id": a.id,
                "hostname": a.hostname,
                "tipo": a.get_asset_type_display(),
                "criticidad": a.criticality,
                "critico": a.criticality in ("high", "critical") or a.stores_phi,
                "datos_clinicos": a.stores_phi,
                "principal": a.id == obj.asset_id,
            }
            for a in filas
        ]

    def get_catalogo_cve(self, obj):
        if not obj.cve:
            return None
        c = CatalogoCVE.objects.filter(cve_id=obj.cve).first()
        return CatalogoCVESerializer(c).data if c else None

    class Meta(VulnerabilityListSerializer.Meta):
        fields = VulnerabilityListSerializer.Meta.fields + [
            "description",
            "ai_summary",
            "ai_remediation_steps",
            "ai_rollback_risk",
            "ai_analyzed_at",
            "control_ids",
            "control_codes",
            "category_display",
            "last_seen_at",
            "riesgo_sugerido_en",
            "riesgo_corregido_por",
            "riesgo_corregido_en",
            "motivo_correccion",
            "explicacion",
            "activos_relacionados",
            "catalogo_cve",
        ]


class CorregirClasificacionSerializer(serializers.Serializer):
    riesgo = serializers.ChoiceField(choices=NIVELES_RIESGO)
    motivo = serializers.CharField(max_length=1000)


class EntrenamientoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntrenamientoModelo
        fields = [
            "algoritmo", "entrenado_en", "muestras_reales", "muestras_sinteticas", "muestras_prueba",
            "accuracy", "f1_macro", "parametros",
        ]


class CatalogoCVESerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoCVE
        fields = [
            "cve_id", "descripcion", "cvss_score", "cvss_vector", "severidad", "publicado_en",
            "modificado_en", "kev", "kev_agregado_en", "fuente", "incorporado_en",
        ]


class SincronizacionCVESerializer(serializers.ModelSerializer):
    class Meta:
        model = SincronizacionCVE
        fields = [
            "id", "iniciado_en", "terminado_en", "ok", "nuevos", "actualizados", "kev_marcados",
            "hallazgos_enriquecidos", "error",
        ]
