from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.mixins import OrganizationScopedMixin
from governance.audit import registrar
from governance.models import NivelAutonomia

from .models import Role
from .models import User as Profile
from .serializers import (
    CambiarClaveSerializer,
    MeSerializer,
    MeUpdateSerializer,
    MiembroCrearSerializer,
    MiembroSerializer,
    OrganizationSerializer,
    RestablecerClaveSerializer,
)


def _perfil(request):
    profile = getattr(request.user, "profile", None)
    if profile is None:
        raise PermissionDenied("El usuario no tiene un perfil de organización asociado.")
    return profile


class MeView(APIView):
    """
    GET /api/auth/me/ - quién está conectado. El frontend lo usa para
    mostrar el nombre real de la organización y el rol en la barra
    superior, en vez de un texto fijo ("Clínica San Lucas" a secas
    para cualquier usuario).

    PATCH /api/auth/me/ - el usuario cambia su propio correo desde
    Configuración > Mi cuenta. Es su cuenta, no datos de la
    organización, así que aquí sí se le permite al Auditor (por eso
    se usa IsAuthenticated en vez del permiso por rol).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response(
                {"detail": "El usuario no tiene un perfil de organización asociado."}, status=403
            )
        return Response(MeSerializer(profile).data)

    def patch(self, request):
        profile = _perfil(request)
        serializer = MeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        anterior = request.user.email
        request.user.email = serializer.validated_data["email"]
        request.user.save(update_fields=["email"])
        registrar(
            organization=profile.organization,
            actor=request.user.username,
            accion="cuenta_actualizada",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="usuario",
            objeto_id=request.user.pk,
            detalle={"campo": "email", "de": anterior, "a": request.user.email},
        )
        return Response(MeSerializer(profile).data)


class CambiarClaveView(APIView):
    """POST /api/auth/cambiar-clave/ {clave_actual, clave_nueva}. Cualquier rol, solo sobre su propia cuenta."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _perfil(request)
        serializer = CambiarClaveSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["clave_nueva"])
        request.user.save(update_fields=["password"])
        registrar(
            organization=profile.organization,
            actor=request.user.username,
            accion="clave_cambiada",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="usuario",
            objeto_id=request.user.pk,
        )
        return Response({"detail": "Contraseña actualizada."})


class OrganizacionView(APIView):
    """
    GET /api/organizacion/ - datos de la organización del usuario.
    PATCH /api/organizacion/ - solo el Administrador cambia nombre y RUC.
    El permiso por defecto ya bloquea al Auditor en PATCH.
    """

    def get(self, request):
        return Response(OrganizationSerializer(_perfil(request).organization).data)

    def patch(self, request):
        profile = _perfil(request)
        if profile.role != Role.ADMIN:
            raise PermissionDenied("Solo el rol Administrador puede editar los datos de la organización.")
        org = profile.organization
        antes = OrganizationSerializer(org).data
        serializer = OrganizationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        cambios = {k: {"de": antes[k], "a": serializer.data[k]} for k in ("name", "ruc") if antes[k] != serializer.data[k]}
        registrar(
            organization=org,
            actor=request.user.username,
            accion="organizacion_actualizada",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="organizacion",
            objeto_id=org.id,
            detalle=cambios,
        )
        return Response(serializer.data)


class MiembroViewSet(
    OrganizationScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/usuarios/ - integrantes de la organización (Configuración >
    Usuarios). Todos los roles pueden verlos; solo el Administrador
    crea cuentas, cambia roles, activa/desactiva y restablece claves.
    Nunca sobre sí mismo (para no quedarse sin Administrador ni
    bloquearse por accidente). No hay borrado: una cuenta se desactiva,
    así su rastro en la auditoría sigue teniendo dueño.
    """

    serializer_class = MiembroSerializer
    queryset = Profile.objects.select_related("user").order_by("user__username")
    pagination_class = None
    http_method_names = ["get", "post", "patch", "head", "options"]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.user.profile.role != Role.ADMIN:
            raise PermissionDenied("Solo el rol Administrador puede administrar usuarios.")

    def _registrar(self, accion, miembro, detalle=None):
        registrar(
            organization=self._organization(),
            actor=self.request.user.username,
            accion=accion,
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="usuario",
            objeto_id=miembro.user_id,
            detalle={"usuario": miembro.user.username, **(detalle or {})},
        )

    def _no_sobre_si_mismo(self, miembro, campo):
        if miembro.user_id == self.request.user.pk:
            raise ValidationError({campo: "No puedes hacer esto sobre tu propia cuenta."})

    @transaction.atomic
    def create(self, request):
        serializer = MiembroCrearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        user = get_user_model().objects.create_user(datos["username"], email=datos["email"], password=datos["password"])
        miembro = Profile.objects.create(user=user, organization=self._organization(), role=datos["role"])
        self._registrar("usuario_creado", miembro, {"rol": miembro.role})
        return Response(MiembroSerializer(miembro).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        miembro = serializer.instance
        datos = serializer.validated_data
        rol_antes, activo_antes = miembro.role, miembro.user.is_active
        if "role" in datos and datos["role"] != rol_antes:
            self._no_sobre_si_mismo(miembro, "role")
        nuevo_activo = datos.get("user", {}).get("is_active")
        if nuevo_activo is not None and nuevo_activo != activo_antes:
            self._no_sobre_si_mismo(miembro, "is_active")

        miembro = serializer.save()
        if miembro.role != rol_antes:
            self._registrar("rol_cambiado", miembro, {"de": rol_antes, "a": miembro.role})
        if miembro.user.is_active != activo_antes:
            self._registrar("usuario_activado" if miembro.user.is_active else "usuario_desactivado", miembro)

    @action(detail=True, methods=["post"], url_path="restablecer-clave")
    def restablecer_clave(self, request, pk=None):
        miembro = self.get_object()
        self._no_sobre_si_mismo(miembro, "clave_nueva")
        serializer = RestablecerClaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        miembro.user.set_password(serializer.validated_data["clave_nueva"])
        miembro.user.save(update_fields=["password"])
        self._registrar("clave_restablecida", miembro)
        return Response({"detail": f"Contraseña de {miembro.user.username} restablecida."})
