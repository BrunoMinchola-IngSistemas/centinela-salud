from django.http import FileResponse
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.mixins import OrganizationScopedMixin
from governance.audit import registrar
from governance.models import NivelAutonomia

from .indicadores import resumen_ejecutivo, registrar_snapshot
from .models import FormatoReporte, ReporteGenerado
from .reportes import PeriodicidadNoConfigurada, generar_reporte


class ReporteSerializer(serializers.ModelSerializer):
    formato_display = serializers.CharField(source="get_formato_display", read_only=True)

    class Meta:
        model = ReporteGenerado
        fields = [
            "id", "formato", "formato_display", "periodo_desde", "periodo_hasta", "sha256_hash",
            "automatico", "generado_por", "generado_en", "resumen",
        ]
        read_only_fields = fields


class ReporteViewSet(OrganizationScopedMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """HU21: reportes generados (automáticos o a pedido) y su descarga."""

    serializer_class = ReporteSerializer
    queryset = ReporteGenerado.objects.all()
    modulo = "informes"

    @action(detail=False, methods=["post"])
    def generar(self, request):
        formato = request.data.get("formato", FormatoReporte.PDF)
        if formato not in FormatoReporte.values:
            raise ValidationError({"formato": "Usa 'pdf' o 'xlsx'."})
        org = self._organization()
        try:
            reporte = generar_reporte(org, formato, request.user.username)
        except PeriodicidadNoConfigurada as exc:
            raise ValidationError({"detail": str(exc), "requiere_configuracion": True}) from exc
        return Response(ReporteSerializer(reporte).data, status=201)

    @action(detail=True, methods=["get"])
    def descargar(self, request, pk=None):
        reporte = self.get_object()
        registrar(
            organization=reporte.organization,
            actor=request.user.username,
            accion="reporte_descargado",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="reporte",
            objeto_id=reporte.id,
        )
        nombre = reporte.archivo.name.rsplit("/", 1)[-1]
        return FileResponse(reporte.archivo.open("rb"), as_attachment=True, filename=nombre)


class ResumenEjecutivoView(APIView):
    """HU16/HU20: cuadro de mando de Gerencia, en lenguaje no técnico."""

    modulo = "ejecutivo"

    def get(self, request):
        org = request.user.profile.organization
        # La foto del día se toma al primer acceso (y también la tarea
        # programada la toma cada noche): así siempre hay línea base.
        registrar_snapshot(org)
        return Response(resumen_ejecutivo(org))
