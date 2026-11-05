from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import Role
from common.mixins import OrganizationScopedMixin

from . import agente
from .audit import registrar
from .models import (
    AccionAgente,
    EstadoAccion,
    EstadoSolicitud,
    NivelAutonomia,
    PoliticaAutonomia,
    RegistroAuditoria,
    SolicitudAprobacion,
)
from .serializers import (
    AccionAgenteSerializer,
    PoliticaAutonomiaSerializer,
    ProponerAccionSerializer,
    RegistroAuditoriaSerializer,
    SolicitudAprobacionSerializer,
)

ROLES_EJECUTAN = {Role.ADMIN, Role.IT_OWNER}


class PoliticaAutonomiaViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """HU23: qué nivel de autonomía aplica a cada tipo de acción, por organización."""

    serializer_class = PoliticaAutonomiaSerializer
    queryset = PoliticaAutonomia.objects.all()
    modulo = "gobernanza"
    pagination_class = None

    def check_permissions(self, request):
        super().check_permissions(request)
        # Cambiar cuánta autonomía tiene el agente es una decisión de
        # política: solo el Administrador.
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.user.profile.role != Role.ADMIN:
            raise PermissionDenied("Solo el rol Administrador puede cambiar las políticas de autonomía.")

    def perform_update(self, serializer):
        anterior = serializer.instance.nivel
        politica = serializer.save()
        registrar(
            organization=self._organization(),
            actor=self.request.user.username,
            accion="politica_autonomia_cambiada",
            modalidad=politica.nivel,
            objeto_tipo="politica_autonomia",
            objeto_id=politica.id,
            detalle={"tipo_accion": politica.tipo_accion, "de": anterior, "a": politica.nivel},
        )


class SolicitudAprobacionViewSet(viewsets.ModelViewSet):
    """
    HU24: solicitudes de aprobación para acciones de alto impacto.

    No usa OrganizationScopedMixin porque SolicitudAprobacion no tiene
    un FK directo a Organization (llega a ella vía
    plan -> vulnerability -> organization), así que el filtro y la
    creación se escriben a mano abajo. Decidir (aprobar/rechazar) se
    hace con las acciones dedicadas, no con un PATCH libre, para dejar
    registrado quién decidió y por qué.
    """

    serializer_class = SolicitudAprobacionSerializer
    queryset = SolicitudAprobacion.objects.select_related("plan__vulnerability__organization")
    modulo = "gobernanza"

    def _organization(self):
        profile = getattr(self.request.user, "profile", None)
        if profile is None:
            raise PermissionDenied("El usuario no tiene un perfil de organización asociado.")
        return profile.organization

    def get_queryset(self):
        return super().get_queryset().filter(plan__vulnerability__organization=self._organization())

    def perform_create(self, serializer):
        solicitud = serializer.save()
        agente.avisar_solicitud(solicitud)  # HU24: llega a la Gerencia en el momento
        registrar(
            organization=self._organization(),
            actor=self.request.user.username,
            accion="solicitud_creada",
            modalidad=NivelAutonomia.CON_APROBACION,
            objeto_tipo="remediation_plan",
            objeto_id=solicitud.plan_id,
            detalle={"solicitud_id": str(solicitud.id), "tipo_accion": solicitud.tipo_accion},
        )

    def _decidir(self, request, estado, accion_log):
        # HU24: la decisión sobre una acción de alto impacto la toma la
        # dirección (Gerente General), que en el sistema es el rol
        # Administrador. Un analista o TI puede pedirla, no aprobarla.
        solicitud = self.get_object()
        # HU24 esc. 2: si se escaló, también puede decidir el segundo responsable.
        es_segundo = solicitud.estado == EstadoSolicitud.ESCALADA and solicitud.escalado_a == request.user.username
        if request.user.profile.role != Role.ADMIN and not es_segundo:
            raise PermissionDenied("Solo el rol Administrador (Gerencia) puede aprobar o rechazar acciones de alto impacto.")
        if solicitud.estado not in (EstadoSolicitud.PENDIENTE, EstadoSolicitud.ESCALADA):
            raise ValidationError({"estado": "Esta solicitud ya fue decidida."})
        solicitud.estado = estado
        solicitud.decidido_por = request.user.username
        solicitud.decidido_en = timezone.now()
        solicitud.comentario_decision = request.data.get("comentario", "")
        solicitud.save(update_fields=["estado", "decidido_por", "decidido_en", "comentario_decision"])

        registrar(
            organization=self._organization(),
            actor=request.user.username,
            accion=accion_log,
            modalidad=NivelAutonomia.CON_APROBACION,
            objeto_tipo="remediation_plan",
            objeto_id=solicitud.plan_id,
            detalle={"solicitud_id": str(solicitud.id), "comentario": solicitud.comentario_decision},
        )
        # La acción que estaba bloqueada esperando esta decisión se ejecuta o se rechaza.
        agente.resolver_solicitud(solicitud, estado == EstadoSolicitud.APROBADA, request.user.username)
        return solicitud

    @action(detail=True, methods=["post"])
    def aprobar(self, request, pk=None):
        solicitud = self._decidir(request, EstadoSolicitud.APROBADA, "solicitud_aprobada")
        return Response(SolicitudAprobacionSerializer(solicitud).data)

    @action(detail=True, methods=["post"])
    def rechazar(self, request, pk=None):
        solicitud = self._decidir(request, EstadoSolicitud.RECHAZADA, "solicitud_rechazada")
        return Response(SolicitudAprobacionSerializer(solicitud).data)


class RegistroAuditoriaViewSet(
    OrganizationScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    HU27 / RNF-05: "log no editable ni borrable". A propósito NO hereda
    de ModelViewSet: solo expone list/retrieve/create (vía los mixins
    de arriba), así que no existe ninguna ruta DRF para update,
    partial_update ni destroy, sin importar qué intente mandar el
    cliente.
    """

    serializer_class = RegistroAuditoriaSerializer
    queryset = RegistroAuditoria.objects.all()
    modulo = "auditoria"
    # Filtros para la ventana de auditoría del Administrador
    # (Configuración > Auditoría): por quién, qué acción y sobre qué.
    filterset_fields = ["actor", "accion", "modalidad", "objeto_tipo"]


class AccionAgenteViewSet(
    OrganizationScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    HU18: acciones de remediación que propone el agente y qué pasó con
    cada una según la política de autonomía (ver governance/agente.py).
    POST crea una propuesta; `ejecutar` la corre a mano (TI) cuando
    quedó pendiente; `descartar` la cierra sin ejecutar.
    """

    serializer_class = AccionAgenteSerializer
    queryset = AccionAgente.objects.select_related("plan__vulnerability", "solicitud")
    filterset_fields = ["estado", "tipo_accion", "plan"]
    modulo = "gobernanza"

    def create(self, request, *args, **kwargs):
        datos = ProponerAccionSerializer(data=request.data, context={"request": request})
        datos.is_valid(raise_exception=True)
        accion = agente.proponer_accion(
            datos.validated_data["plan"],
            datos.validated_data["tipo_accion"],
            propuesta_por=request.user.username,
            detalle=datos.validated_data.get("detalle", ""),
        )
        return Response(AccionAgenteSerializer(accion).data, status=201)

    @action(detail=True, methods=["post"])
    def ejecutar(self, request, pk=None):
        if request.user.profile.role not in ROLES_EJECUTAN:
            raise PermissionDenied("Solo TI o la Gerencia ejecutan acciones manualmente.")
        accion = self.get_object()
        try:
            agente.ejecutar_manual(accion, request.user.username)
        except ValueError as exc:
            raise ValidationError({"estado": str(exc)}) from exc
        return Response(AccionAgenteSerializer(accion).data)

    @action(detail=True, methods=["post"])
    def descartar(self, request, pk=None):
        if request.user.profile.role not in ROLES_EJECUTAN:
            raise PermissionDenied("Solo TI o la Gerencia descartan acciones.")
        accion = self.get_object()
        if accion.estado != EstadoAccion.PENDIENTE_MANUAL:
            raise ValidationError({"estado": "Solo se descarta una acción pendiente de ejecución manual."})
        comentario = str(request.data.get("comentario", "")).strip()
        accion.estado = EstadoAccion.DESCARTADA
        accion.motivo = f"Descartada por {request.user.username}. {comentario}".strip()
        accion.save(update_fields=["estado", "motivo"])
        registrar(
            organization=accion.organization,
            actor=request.user.username,
            accion="accion_descartada",
            modalidad=accion.nivel_aplicado,
            objeto_tipo="remediation_plan",
            objeto_id=accion.plan_id,
            detalle={"accion_id": str(accion.id), "tipo_accion": accion.tipo_accion},
        )
        return Response(AccionAgenteSerializer(accion).data)
