import uuid

from django.conf import settings
from django.db import models


class Organization(models.Model):
    """Una PyME de salud (tenant). Toda la data cuelga de una organización."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    ruc = models.CharField("RUC / identificador fiscal", max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    ADMIN = "admin", "Administrador"
    ANALYST = "analyst", "Analista de seguridad"
    IT_OWNER = "it_owner", "Responsable de TI"
    AUDITOR = "auditor", "Auditor"


class User(models.Model):
    """
    Perfil extendido 1-a-1 sobre el usuario de Django (que maneja
    autenticación/clave). Separado para no tocar el modelo de auth
    si luego se integra SSO/MFA corporativo.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ANALYST)
    mfa_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"
