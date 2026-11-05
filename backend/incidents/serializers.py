from rest_framework import serializers

from .models import IncidenteReportado


class IncidenteReportadoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    evaluacion_categoria_display = serializers.CharField(read_only=True)

    class Meta:
        model = IncidenteReportado
        fields = [
            "id",
            "descripcion",
            "lugar",
            "ocurrido_en",
            "reportado_por",
            "estado",
            "estado_display",
            "creado_en",
            "evaluacion_categoria",
            "evaluacion_categoria_display",
            "evaluacion_severidad",
            "evaluacion_resumen",
            "evaluacion_recomendacion",
            "evaluado_en",
        ]
        read_only_fields = [
            "reportado_por", "estado", "creado_en", "evaluacion_categoria", "evaluacion_severidad",
            "evaluacion_resumen", "evaluacion_recomendacion", "evaluado_en",
        ]
        # HU30 esc. 2: los 3 campos son obligatorios; si falta alguno no se procesa el envío.
        extra_kwargs = {
            "descripcion": {"error_messages": {"required": "Cuéntanos qué pasó.", "blank": "Cuéntanos qué pasó."}},
            "lugar": {"error_messages": {"required": "Indica dónde pasó.", "blank": "Indica dónde pasó."}},
            "ocurrido_en": {"error_messages": {"required": "Indica cuándo pasó.", "null": "Indica cuándo pasó."}},
        }
