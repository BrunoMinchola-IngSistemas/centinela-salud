import uuid

from django.db import models

from accounts.models import Organization


class AssetType(models.TextChoices):
    SERVER = "server", "Servidor"
    WORKSTATION = "workstation", "Estación"
    MEDICAL_DEVICE = "medical_device", "Dispositivo médico"
    APPLICATION = "application", "Aplicación"
    NETWORK_DEVICE = "network_device", "Equipo de red"


class Criticality(models.TextChoices):
    CRITICAL = "critical", "Crítica"
    HIGH = "high", "Alta"
    MEDIUM = "medium", "Media"
    LOW = "low", "Baja"


class Asset(models.Model):
    """
    Un activo descubierto o registrado: servidor, estación, dispositivo
    médico o aplicación. Es el nodo contra el que se cuelgan
    vulnerabilidades y agentes de monitoreo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="assets")
    hostname = models.CharField(max_length=150)
    asset_type = models.CharField(max_length=20, choices=AssetType.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    operating_system = models.CharField(max_length=150, blank=True)
    criticality = models.CharField(max_length=10, choices=Criticality.choices, default=Criticality.MEDIUM)
    stores_phi = models.BooleanField(
        "Almacena datos de pacientes (PHI)",
        default=False,
        help_text="Marca si el activo procesa o almacena información de salud identificable.",
    )
    wazuh_agent_id = models.CharField(max_length=50, blank=True)
    wazuh_agent_online = models.BooleanField(default=False)
    tags = models.JSONField(default=list, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hostname"]
        indexes = [models.Index(fields=["organization", "asset_type"])]
        constraints = [
            models.UniqueConstraint(fields=["organization", "hostname"], name="uniq_asset_hostname_per_org")
        ]

    def __str__(self):
        return self.hostname

    @property
    def open_vulnerability_count(self):
        return self.vulnerabilities.exclude(status="closed").count()
