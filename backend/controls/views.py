from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import Role
from common.mixins import OrganizationScopedMixin
from governance.audit import registrar
from governance.models import NivelAutonomia
from informes.exportar import exportar_tabla
from integrations.qwen import suggest_control_improvement

from .models import Control
from .serializers import ControlSerializer
from .services import cumplimiento_global, cumplimiento_ley_29733, cumplimiento_por_dominio, matriz_aplicables, recomendaciones

# HU13: quién puede marcar el estado de implementación de un control.
ROLES_EDITAN_ESTADO = {Role.ADMIN, Role.COMPLIANCE, Role.IT_OWNER}
NIVEL = {"alto": "Alta", "medio": "Media", "bajo": "Baja"}
COSTO = {"alto": "Alto", "medio": "Medio", "bajo": "Bajo"}


class ControlViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    queryset = Control.objects.prefetch_related("mappings", "vulnerabilities", "assessments").all()
    serializer_class = ControlSerializer
    # El catálogo completo (~34 controles) cabe en una sola página y la
    # vista de cumplimiento por tema necesita verlos todos juntos.
    pagination_class = None
    modulo = "controles"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_update(self, serializer):
        profile = self.request.user.profile
        if profile.role not in ROLES_EDITAN_ESTADO:
            raise PermissionDenied("Solo Cumplimiento, TI o la Gerencia pueden cambiar el estado de un control.")
        anterior = serializer.instance.estado_implementacion
        control = serializer.save(estado_actualizado_en=timezone.now(), estado_actualizado_por=self.request.user.username)
        if control.estado_implementacion != anterior:
            registrar(
                organization=control.organization,
                actor=self.request.user.username,
                accion="control_estado_cambiado",
                modalidad=NivelAutonomia.ASISTIDO,
                objeto_tipo="control",
                objeto_id=control.id,
                detalle={"control": control.iso_code, "de": anterior, "a": control.estado_implementacion},
            )

    @action(detail=True, methods=["post"])
    def assess(self, request, pk=None):
        """
        Evaluación con IA: le pasa a Qwen el control y sus hallazgos
        asociados y devuelve una recomendación de mejora.
        """
        control = self.get_object()
        assessment = suggest_control_improvement(control)
        return Response({"control": control.id, "score": assessment.score, "recommendation": assessment.recommendation})

    @action(detail=False, methods=["get"], url_path="por-tema")
    def por_tema(self, request):
        """HU13: % de cumplimiento por dominio (implementados = 100, parciales = 50), recalculado en cada consulta."""
        org = self._organization()
        return Response(
            {
                "dominios": cumplimiento_por_dominio(org),
                "global": cumplimiento_global(org),
                "ley_29733": cumplimiento_ley_29733(org),
                "actualizado_en": timezone.now(),
            }
        )

    @action(detail=False, methods=["get"], url_path="matriz-aplicables")
    def matriz_aplicables(self, request):
        """HU12: matriz de controles aplicables agrupada por dominio, según el nivel de madurez."""
        org = self._organization()
        if not org.nivel_madurez:
            raise ValidationError(
                {
                    "detail": "Debe registrar el nivel de madurez de la organización antes de generar la matriz de controles aplicables.",
                    "requiere_configuracion": True,
                }
            )
        return Response(matriz_aplicables(org))

    @action(detail=False, methods=["get"])
    def recomendaciones(self, request):
        """HU15: controles pendientes ordenados por criticidad y costo; ?formato=pdf|xlsx|csv exporta el plan de acción."""
        org = self._organization()
        filas = recomendaciones(org)
        formato = request.query_params.get("formato")
        if formato:
            if not filas:
                raise ValidationError({"detail": "No existen controles pendientes por recomendar."})
            return exportar_tabla(
                "plan_accion_controles",
                f"Plan de acción ISO/IEC 27001 · {org.name}",
                ["#", "Control", "Acción recomendada", "Criticidad", "Costo", "Hallazgos abiertos", "Por qué"],
                [[f["prioridad"], f["codigo"], f["accion"], NIVEL[f["criticidad"]], COSTO[f["costo"]], f["hallazgos_abiertos"], f["motivo"]]
                 for f in filas],
                formato,
                anchos=(4, 7, 34, 9, 8, 9, 40),
                intro="Controles pendientes o parciales ordenados por criticidad (alta primero) y costo estimado (bajo primero).",
            )
        if not filas:
            return Response({"recomendaciones": [], "mensaje": "No existen controles pendientes por recomendar."})
        return Response({"recomendaciones": filas, "mensaje": ""})
