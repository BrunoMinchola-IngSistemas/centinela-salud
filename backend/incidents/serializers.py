from rest_framework import serializers

from .models import IncidenteReportado


class IncidenteReportadoSerializer(serializers.ModelSerializer):
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)

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
        ]
        read_only_fields = ["reportado_por", "estado", "creado_en"]
