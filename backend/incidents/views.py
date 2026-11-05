from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import Role
from common.mixins import OrganizationScopedMixin
from common.privacidad import seudonimizar_texto
from governance.audit import registrar
from governance.models import NivelAutonomia
from notificaciones.models import NivelNotificacion, TipoNotificacion
from notificaciones.servicios import notificar

from .evaluacion import evaluar
from .models import EstadoIncidente, IncidenteReportado
from .serializers import IncidenteReportadoSerializer

ROLES_GESTIONAN = {Role.ADMIN, Role.IT_OWNER, Role.ANALYST}
NIVEL_AVISO = {"critical": NivelNotificacion.CRITICA, "high": NivelNotificacion.ADVERTENCIA}


class IncidenteReportadoViewSet(
    OrganizationScopedMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """
    HU30: reportar un incidente con 3 campos (qué, dónde, cuándo).
    Al recibirlo, el agente lo evalúa y TI recibe la evaluación en el
    momento (notificación en la consola + correo). El Personal
    administrativo/clínico ve solo sus propios reportes.
    """

    serializer_class = IncidenteReportadoSerializer
    queryset = IncidenteReportado.objects.all()
    modulo = "incidentes"

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.profile.role == Role.STAFF:
            qs = qs.filter(reportado_por=self.request.user.username)
        return qs

    def perform_create(self, serializer):
        datos = serializer.validated_data
        evaluacion = evaluar(datos["descripcion"], datos["lugar"])  # sobre el texto original
        incidente = serializer.save(
            organization=self._organization(),
            reportado_por=self.request.user.username,
            # Ley 29733: se guarda seudonimizado (DNI, correos, teléfonos, N.° de historia clínica).
            descripcion=seudonimizar_texto(datos["descripcion"]),
            lugar=seudonimizar_texto(datos["lugar"]),
            evaluacion_categoria=evaluacion["categoria"],
            evaluacion_severidad=evaluacion["severidad"],
            evaluacion_resumen=evaluacion["resumen"],
            evaluacion_recomendacion=evaluacion["recomendacion"],
            evaluado_en=timezone.now(),
        )
        registrar(
            organization=incidente.organization,
            actor=self.request.user.username,
            accion="incidente_reportado",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="incidente",
            objeto_id=incidente.id,
            detalle={"lugar": incidente.lugar, "categoria": incidente.evaluacion_categoria, "severidad": incidente.evaluacion_severidad},
        )
        roles = (Role.IT_OWNER, Role.ADMIN) if incidente.evaluacion_severidad == "critical" else (Role.IT_OWNER,)
        notificar(
            organization=incidente.organization,
            tipo=TipoNotificacion.INCIDENTE,
            nivel=NIVEL_AVISO.get(incidente.evaluacion_severidad, NivelNotificacion.INFO),
            titulo=f"Incidente reportado: {incidente.get_evaluacion_categoria_display()} ({incidente.lugar})",
            mensaje=f"{incidente.evaluacion_resumen} Qué hacer primero: {incidente.evaluacion_recomendacion}",
            enlace="/incidentes",
            roles=roles,
            objeto_tipo="incidente",
            objeto_id=incidente.id,
        )

    @action(detail=True, methods=["post"], url_path="cambiar-estado")
    def cambiar_estado(self, request, pk=None):
        if request.user.profile.role not in ROLES_GESTIONAN:
            raise PermissionDenied("Solo TI, el Analista o la Gerencia cambian el estado de un incidente.")
        incidente = self.get_object()
        estado = request.data.get("estado")
        if estado not in EstadoIncidente.values:
            raise ValidationError({"estado": "Usa reportado, en_revision o cerrado."})
        anterior = incidente.estado
        incidente.estado = estado
        incidente.save(update_fields=["estado"])
        registrar(
            organization=incidente.organization,
            actor=request.user.username,
            accion="incidente_estado_cambiado",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="incidente",
            objeto_id=incidente.id,
            detalle={"de": anterior, "a": estado},
        )
        return Response(IncidenteReportadoSerializer(incidente).data)
