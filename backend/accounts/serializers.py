from rest_framework import serializers

from .models import Organization, User


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "ruc"]


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

    class Meta:
        model = User
        fields = ["username", "email", "role", "role_display", "organization", "mfa_enabled"]
