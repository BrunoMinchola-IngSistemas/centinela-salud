from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Organization, Role, User


class OrganizationSerializer(serializers.ModelSerializer):
    nivel_madurez_display = serializers.CharField(source="get_nivel_madurez_display", read_only=True, default="")
    periodicidad_reporte_display = serializers.CharField(source="get_periodicidad_reporte_display", read_only=True)
    responsable_escalamiento_nombre = serializers.CharField(source="responsable_escalamiento.username", read_only=True, default="")

    class Meta:
        model = Organization
        fields = [
            "id", "name", "ruc", "rango_red", "nivel_madurez", "nivel_madurez_display", "periodicidad_reporte",
            "periodicidad_reporte_display", "ultimo_reporte_en", "ejecucion_autonoma_activa",
            "responsable_escalamiento", "responsable_escalamiento_nombre",
        ]
        read_only_fields = ["id", "ultimo_reporte_en"]

    def validate_rango_red(self, value):
        value = (value or "").strip()
        if not value:
            return value
        from assets.discovery import ObjetivoInvalido, validar_cidr

        try:
            return str(validar_cidr(value))
        except ObjetivoInvalido as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_responsable_escalamiento(self, user):
        if user is not None and getattr(getattr(user, "profile", None), "organization_id", None) != self.instance.id:
            raise serializers.ValidationError("El segundo responsable debe pertenecer a la organización.")
        return user


class MeSerializer(serializers.ModelSerializer):
    """
    Lo que pinta la barra superior de la consola: quién está
    conectado, con qué rol y en qué organización. Antes esto venía
    hardcodeado en el frontend ("Clínica San Lucas" fijo en
    AppShell.jsx) sin importar quién hubiera iniciado sesión.
    """

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    organization = OrganizationSerializer(read_only=True)
    modulos = serializers.SerializerMethodField()
    admin_django = serializers.SerializerMethodField()

    def get_modulos(self, obj):
        from common.modulos import modulos_de

        return modulos_de(obj.role)

    def get_admin_django(self, obj):
        from django.conf import settings

        return bool(settings.ADMIN_DJANGO_HABILITADO and obj.user.is_staff)

    class Meta:
        model = User
        fields = ["username", "email", "role", "role_display", "organization", "mfa_enabled", "modulos", "admin_django"]


def _clave_robusta(valor, user=None):
    """Aplica las reglas de AUTH_PASSWORD_VALIDATORS (mínimo 10, no común, no solo números)."""
    try:
        validate_password(valor, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return valor


class MeUpdateSerializer(serializers.Serializer):
    """Lo único que un usuario puede cambiar de su propia cuenta desde Configuración: el correo."""

    email = serializers.EmailField(allow_blank=True)


class CambiarClaveSerializer(serializers.Serializer):
    clave_actual = serializers.CharField(write_only=True)
    clave_nueva = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        user = self.context["request"].user
        if not user.check_password(data["clave_actual"]):
            raise serializers.ValidationError({"clave_actual": "La contraseña actual no es correcta."})
        if data["clave_actual"] == data["clave_nueva"]:
            raise serializers.ValidationError({"clave_nueva": "La contraseña nueva debe ser distinta a la actual."})
        try:
            _clave_robusta(data["clave_nueva"], user)
        except serializers.ValidationError as exc:
            raise serializers.ValidationError({"clave_nueva": exc.detail}) from exc
        return data


class MiembroSerializer(serializers.ModelSerializer):
    """
    Un integrante de la organización, visto desde Configuración >
    Usuarios. El Administrador puede cambiar el rol y activar o
    desactivar la cuenta; el resto se lee del usuario de Django.
    """

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    last_login = serializers.DateTimeField(source="user.last_login", read_only=True)
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "user_id", "username", "email", "role", "role_display", "is_active", "mfa_enabled", "bloqueado",
            "last_login", "date_joined",
        ]
        read_only_fields = ["mfa_enabled", "user_id"]

    bloqueado = serializers.BooleanField(source="esta_bloqueado", read_only=True)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        if "is_active" in user_data:
            instance.user.is_active = user_data["is_active"]
            instance.user.save(update_fields=["is_active"])
        return super().update(instance, validated_data)


class MiembroCrearSerializer(serializers.Serializer):
    """Alta de un usuario por el Administrador (Configuración > Usuarios)."""

    username = serializers.RegexField(r"^[\w.@+-]{3,150}$", error_messages={"invalid": "Solo letras, números y . @ + - _ (mínimo 3)."})
    email = serializers.EmailField(allow_blank=True, required=False, default="")
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.ANALYST)

    def validate_password(self, value):
        return _clave_robusta(value)

    def validate_username(self, value):
        from django.contrib.auth import get_user_model

        if get_user_model().objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese nombre.")
        return value


class RestablecerClaveSerializer(serializers.Serializer):
    clave_nueva = serializers.CharField(write_only=True, min_length=8)

    def validate_clave_nueva(self, value):
        return _clave_robusta(value)
