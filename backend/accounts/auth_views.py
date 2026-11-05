"""
HU29: inicio de sesión seguro.

- Bloqueo temporal tras 5 intentos fallidos consecutivos (contraseña o
  código del segundo factor): 15 minutos. Se avisa a la Gerencia y
  queda en la auditoría.
- Segundo factor TOTP si la persona lo activó (Configuración > Mi cuenta).
  El primer paso devuelve un `mfa_token` firmado y de corta duración
  (5 min); el token de sesión recién se entrega al validar el código.
- Cada inicio de sesión rota el token (se invalida el anterior) y el
  token expira a las TOKEN_TTL_HORAS horas (ver common/authentication).
- Límite de peticiones por IP (throttle "login") contra fuerza bruta
  distribuida entre muchas cuentas.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from governance.audit import registrar
from governance.models import NivelAutonomia
from notificaciones.models import NivelNotificacion, TipoNotificacion
from notificaciones.servicios import notificar

from . import mfa
from .models import Role

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 15
SAL_MFA = "centinela-mfa-login"
MFA_MAX_SEGUNDOS = 300
CREDENCIALES_INVALIDAS = "Usuario o contraseña incorrectos."


def _bloqueado(perfil):
    minutos = max(1, int((perfil.bloqueado_hasta - timezone.now()).total_seconds() // 60) + 1)
    return Response(
        {"detail": f"Cuenta bloqueada temporalmente por {MAX_INTENTOS} intentos fallidos. Intenta de nuevo en {minutos} minuto(s).",
         "bloqueado_hasta": perfil.bloqueado_hasta},
        status=status.HTTP_423_LOCKED,
    )


def _registrar_fallo(perfil, motivo):
    perfil.intentos_fallidos += 1
    bloquear = perfil.intentos_fallidos >= MAX_INTENTOS
    if bloquear:
        perfil.bloqueado_hasta = timezone.now() + timedelta(minutes=MINUTOS_BLOQUEO)
        perfil.intentos_fallidos = 0
    perfil.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
    if bloquear:
        registrar(
            organization=perfil.organization,
            actor="sistema",
            accion="cuenta_bloqueada",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="usuario",
            objeto_id=perfil.user_id,
            detalle={"usuario": perfil.user.username, "motivo": motivo, "minutos": MINUTOS_BLOQUEO},
        )
        notificar(
            organization=perfil.organization,
            tipo=TipoNotificacion.SEGURIDAD,
            nivel=NivelNotificacion.ADVERTENCIA,
            titulo=f"Cuenta bloqueada: {perfil.user.username}",
            mensaje=f"{MAX_INTENTOS} intentos fallidos de inicio de sesión ({motivo}). Bloqueo de {MINUTOS_BLOQUEO} minutos.",
            enlace="/configuracion",
            roles=(Role.ADMIN,),
        )
    return bloquear


def _emitir_token(user, perfil, con_mfa):
    perfil.intentos_fallidos = 0
    perfil.bloqueado_hasta = None
    perfil.save(update_fields=["intentos_fallidos", "bloqueado_hasta"])
    Token.objects.filter(user=user).delete()  # rotación: una sesión activa por persona
    token = Token.objects.create(user=user)
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
    registrar(
        organization=perfil.organization,
        actor=user.username,
        accion="inicio_sesion",
        modalidad=NivelAutonomia.ASISTIDO,
        objeto_tipo="usuario",
        objeto_id=user.pk,
        detalle={"mfa": con_mfa},
    )
    return Response({"token": token.key, "expira_en_horas": settings.TOKEN_TTL_HORAS})


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=256, trim_whitespace=False)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        datos = LoginSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        username = datos.validated_data["username"]
        user_model = get_user_model()
        existente = user_model.objects.filter(username=username).select_related("profile").first()
        perfil = getattr(existente, "profile", None) if existente else None
        if perfil is not None and perfil.esta_bloqueado:
            return _bloqueado(perfil)

        user = authenticate(request, username=username, password=datos.validated_data["password"])
        if user is None:
            if perfil is not None and existente.is_active and _registrar_fallo(perfil, "contraseña incorrecta"):
                return _bloqueado(perfil)
            return Response({"detail": CREDENCIALES_INVALIDAS}, status=status.HTTP_400_BAD_REQUEST)

        perfil = getattr(user, "profile", None)
        if perfil is None:
            return Response({"detail": "El usuario no tiene un perfil de organización asociado."}, status=403)
        if perfil.mfa_enabled:
            mfa_token = signing.dumps({"uid": user.pk}, salt=SAL_MFA)
            return Response({"mfa_requerido": True, "mfa_token": mfa_token})
        return _emitir_token(user, perfil, con_mfa=False)


class LoginMFASerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    codigo = serializers.CharField(max_length=12)


class LoginMFAView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        datos = LoginMFASerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        try:
            carga = signing.loads(datos.validated_data["mfa_token"], salt=SAL_MFA, max_age=MFA_MAX_SEGUNDOS)
        except signing.BadSignature:
            return Response({"detail": "La verificación expiró. Vuelve a ingresar tu usuario y contraseña."}, status=400)
        user = get_user_model().objects.filter(pk=carga.get("uid"), is_active=True).select_related("profile").first()
        perfil = getattr(user, "profile", None) if user else None
        if perfil is None or not perfil.mfa_enabled:
            return Response({"detail": CREDENCIALES_INVALIDAS}, status=400)
        if perfil.esta_bloqueado:
            return _bloqueado(perfil)
        if not mfa.verificar(perfil.mfa_secret, datos.validated_data["codigo"]):
            if _registrar_fallo(perfil, "código de segundo factor incorrecto"):
                return _bloqueado(perfil)
            return Response({"detail": "Código de verificación incorrecto."}, status=400)
        return _emitir_token(user, perfil, con_mfa=True)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)


class CodigoSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=12)


class MFAView(APIView):
    """
    GET    /api/auth/mfa/            -> {activo}
    POST   /api/auth/mfa/iniciar/    -> genera secreto + QR (aún no activo)
    POST   /api/auth/mfa/activar/    -> {codigo} confirma y activa
    POST   /api/auth/mfa/desactivar/ -> {codigo} desactiva
    Cualquier rol, solo sobre su propia cuenta.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"activo": request.user.profile.mfa_enabled})

    def post(self, request, paso):
        perfil = request.user.profile
        if paso == "iniciar":
            if perfil.mfa_enabled:
                return Response({"detail": "El segundo factor ya está activo."}, status=400)
            perfil.mfa_secret = mfa.nuevo_secreto()
            perfil.save(update_fields=["mfa_secret"])
            enlace = mfa.uri(perfil.mfa_secret, request.user.username)
            return Response({"secreto": perfil.mfa_secret, "otpauth_uri": enlace, "qr": mfa.qr_svg_data_uri(enlace)})

        datos = CodigoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        if not mfa.verificar(perfil.mfa_secret, datos.validated_data["codigo"]):
            return Response({"codigo": ["Código incorrecto. Revisa la hora del celular y vuelve a intentar."]}, status=400)
        if paso == "activar":
            perfil.mfa_enabled = True
            perfil.save(update_fields=["mfa_enabled"])
        elif paso == "desactivar":
            perfil.mfa_enabled = False
            perfil.mfa_secret = ""
            perfil.save(update_fields=["mfa_enabled", "mfa_secret"])
        else:
            return Response(status=404)
        registrar(
            organization=perfil.organization,
            actor=request.user.username,
            accion="mfa_activado" if perfil.mfa_enabled else "mfa_desactivado",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="usuario",
            objeto_id=request.user.pk,
        )
        return Response({"activo": perfil.mfa_enabled})
