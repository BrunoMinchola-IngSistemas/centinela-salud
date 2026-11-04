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


class Exposure(models.TextChoices):
    """Exposición de red del activo, usada por las reglas R1-R3 de prioridad contextual."""

    INTERNET = "internet", "Expuesto a Internet"
    PERIMETRAL = "perimetral", "Perimetral (DMZ)"
    INTERNA = "interna", "Solo red interna"


class DiscoverySource(models.TextChoices):
    """Cómo llegó el activo al inventario."""

    MANUAL = "manual", "Registro manual"
    RED_LOCAL = "red_local", "Barrido de red local"
    WAZUH = "wazuh", "Agentes Wazuh"
    OPENVAS = "openvas", "Escaneo OpenVAS"


class AssetStatus(models.TextChoices):
    """
    Estado operativo que se muestra en el inventario. No se guarda: se
    deriva de si el agente Wazuh está en línea y del resultado del
    último descubrimiento (ver Asset.estado).
    """

    EN_LINEA = "en_linea", "En línea"
    SIN_SENAL = "sin_senal", "Sin señal"
    DESCONOCIDO = "desconocido", "Sin verificar"


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
    mac_address = models.CharField(max_length=17, blank=True)
    operating_system = models.CharField(max_length=150, blank=True)
    discovery_source = models.CharField(max_length=12, choices=DiscoverySource.choices, default=DiscoverySource.MANUAL)
    last_discovered_at = models.DateTimeField(null=True, blank=True, help_text="Última vez que un descubrimiento lo encontró.")
    reachable = models.BooleanField(
        null=True, blank=True, help_text="Resultado del último descubrimiento: respondió (True), no respondió (False) o nunca se verificó (None)."
    )
    criticality = models.CharField(max_length=10, choices=Criticality.choices, default=Criticality.MEDIUM)
    exposure = models.CharField(
        "Exposición", max_length=12, choices=Exposure.choices, default=Exposure.INTERNA
    )
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Si cambia la exposición, criticidad o si guarda datos clínicos,
        # la prioridad contextual de sus hallazgos cambia (reglas R1-R5).
        for vuln in self.vulnerabilities.all():
            vuln.save(update_fields=["contextual_priority", "priority_rules"])

    @property
    def open_vulnerability_count(self):
        return self.vulnerabilities.exclude(status="closed").count()

    @property
    def estado(self) -> str:
        if self.wazuh_agent_online or self.reachable is True:
            return AssetStatus.EN_LINEA
        if self.reachable is False:
            return AssetStatus.SIN_SENAL
        return AssetStatus.DESCONOCIDO


class DiscoveryRunStatus(models.TextChoices):
    OK = "ok", "Completado"
    ERROR = "error", "Con error"


class DiscoveryRun(models.Model):
    """
    Una ejecución del descubrimiento de activos (HU de inventario):
    quién la lanzó, contra qué (un rango de red o los agentes Wazuh) y
    el informe de lo que encontró. Se conserva como historial para que
    el Administrador vea cómo cambia el parque tecnológico en el tiempo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="discovery_runs")
    source = models.CharField(max_length=12, choices=DiscoverySource.choices)
    target = models.CharField(max_length=60, blank=True, help_text="Rango CIDR barrido, vacío para fuentes sin rango.")
    started_by = models.CharField(max_length=150)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=DiscoveryRunStatus.choices, default=DiscoveryRunStatus.OK)
    error = models.TextField(blank=True)
    found_count = models.PositiveIntegerField(default=0)
    new_count = models.PositiveIntegerField(default=0)
    unreachable_count = models.PositiveIntegerField(default=0)
    hosts = models.JSONField(default=list, blank=True, help_text="Detalle por host: ip, hostname, mac, nuevo, activo_id.")

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.get_source_display()} {self.target} ({self.started_at:%Y-%m-%d %H:%M})"
