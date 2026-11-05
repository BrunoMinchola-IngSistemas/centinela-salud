import uuid

from django.conf import settings
from django.db import models


class NivelMadurez(models.IntegerChoices):
    """HU12: nivel de madurez de seguridad de la organización (escala tipo CMMI)."""

    INICIAL = 1, "1 · Inicial (procesos informales)"
    GESTIONADO = 2, "2 · Gestionado (prácticas básicas repetibles)"
    DEFINIDO = 3, "3 · Definido (procesos documentados)"
    MEDIDO = 4, "4 · Gestionado cuantitativamente (se mide)"
    OPTIMIZADO = 5, "5 · Optimizado (mejora continua)"


class PeriodicidadReporte(models.TextChoices):
    """HU21: cada cuánto el agente genera el reporte automático."""

    SEMANAL = "semanal", "Semanal"
    MENSUAL = "mensual", "Mensual"


class Organization(models.Model):
    """Una PyME de salud (tenant). Toda la data cuelga de una organización."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    ruc = models.CharField("RUC / identificador fiscal", max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # HU01: rango de red que el agente barre en el descubrimiento.
    rango_red = models.CharField(
        "Rango de red para descubrimiento", max_length=60, blank=True, help_text="CIDR privado, p. ej. 192.168.1.0/24."
    )
    # HU12: madurez declarada; sin ella no se genera la matriz de controles aplicables.
    nivel_madurez = models.PositiveSmallIntegerField(choices=NivelMadurez.choices, null=True, blank=True)
    # HU21: periodicidad del reporte automático.
    periodicidad_reporte = models.CharField(max_length=10, choices=PeriodicidadReporte.choices, blank=True)
    ultimo_reporte_en = models.DateTimeField(null=True, blank=True)
    # HU18: interruptor general de la ejecución autónoma (lista blanca).
    ejecucion_autonoma_activa = models.BooleanField(
        default=True, help_text="Si está apagado, el agente no ejecuta nada solo: deja todo pendiente de aprobación manual."
    )
    # HU24: segundo responsable al que se escala una solicitud sin respuesta.
    responsable_escalamiento = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Role(models.TextChoices):
    """
    HU28: los 4 roles del backlog (Gerencia, TI, Cumplimiento, Personal
    administrativo) más los 2 que ya existían en el sistema (Analista de
    seguridad y Auditor de solo lectura). Gerencia = Administrador.
    Qué módulos ve cada rol está en common/modulos.py.
    """

    ADMIN = "admin", "Administrador (Gerencia)"
    IT_OWNER = "it_owner", "Responsable de TI"
    COMPLIANCE = "compliance", "Oficial de Cumplimiento"
    STAFF = "staff", "Personal administrativo / clínico"
    ANALYST = "analyst", "Analista de seguridad"
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

    # HU29: segundo factor (TOTP, app autenticadora) y bloqueo por intentos.
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True, help_text="Secreto TOTP en base32. Nunca se devuelve por la API.")
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def esta_bloqueado(self):
        from django.utils import timezone

        return bool(self.bloqueado_hasta and self.bloqueado_hasta > timezone.now())
