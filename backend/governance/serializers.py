from rest_framework import serializers

from .models import PoliticaAutonomia, RegistroAuditoria, SolicitudAprobacion


class PoliticaAutonomiaSerializer(serializers.ModelSerializer):
    tipo_accion_display = serializers.CharField(source="get_tipo_accion_display", read_only=True)
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)

    class Meta:
        model = PoliticaAutonomia
        fields = ["id", "tipo_accion", "tipo_accion_display", "nivel", "nivel_display", "actualizado_en"]


class SolicitudAprobacionSerializer(serializers.ModelSerializer):
    tipo_accion_display = serializers.CharField(source="get_tipo_accion_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    vulnerability_title = serializers.CharField(source="plan.vulnerability.title", read_only=True)
    vulnerability_id = serializers.UUIDField(source="plan.vulnerability.id", read_only=True)

    class Meta:
        model = SolicitudAprobacion
        fields = [
            "id",
            "plan",
            "vulnerability_id",
            "vulnerability_title",
            "tipo_accion",
            "tipo_accion_display",
            "riesgo_de_no_actuar",
            "efecto_esperado",
            "estado",
            "estado_display",
            "solicitado_en",
            "plazo",
            "decidido_por",
            "decidido_en",
            "comentario_decision",
            "escalado_a",
        ]
        read_only_fields = ["estado", "decidido_por", "decidido_en", "escalado_a"]


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    modalidad_display = serializers.CharField(source="get_modalidad_display", read_only=True)

    class Meta:
        model = RegistroAuditoria
        fields = [
            "id",
            "actor",
            "accion",
            "modalidad",
            "modalidad_display",
            "objeto_tipo",
            "objeto_id",
            "detalle",
            "creado_en",
        ]
        read_only_fields = fields
