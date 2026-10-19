import uuid

from django.db import models

from accounts.models import Organization
from assets.models import Asset
from controls.models import Control


class SourceType(models.TextChoices):
    """
    De dónde viene un hallazgo. Wazuh y OpenVAS son los motores
    principales de la arquitectura. KASPERSKY (u otro EDR/antivirus
    que la PyME ya tenga licenciado) queda contemplado como fuente
    adicional de alertas, pero no reemplaza al escáner de vulnerabilidades.
    """

    WAZUH = "wazuh", "Wazuh"
    OPENVAS = "openvas", "OpenVAS"
    KASPERSKY = "kaspersky", "Kaspersky (opcional)"
    MANUAL = "manual", "Registro manual"


class VulnerabilitySource(models.Model):
    """
    Configuración de una integración concreta (una instancia de Wazuh,
    un servidor GVM, una cuenta de Kaspersky Security Center, etc.).
    No guarda credenciales en texto plano: solo referencia a dónde
    están (variable de entorno / secret manager) y el estado de salud.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    name = models.CharField(max_length=100)
    base_url = models.CharField(max_length=255, blank=True)
    credential_ref = models.CharField(
        max_length=150, blank=True, help_text="Referencia al secreto (p. ej. en AWS Secrets Manager), nunca la clave."
    )
    is_active = models.BooleanField(default=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_ok = models.BooleanField(null=True)

    class Meta:
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.get_source_type_display()} · {self.name}"


class Severity(models.TextChoices):
    CRITICAL = "critical", "Crítica"
    HIGH = "high", "Alta"
    MEDIUM = "medium", "Media"
    LOW = "low", "Baja"


class VulnerabilityStatus(models.TextChoices):
    OPEN = "open", "Abierta"
    IN_PLAN = "in_plan", "En plan"
    IN_VERIFICATION = "in_verification", "En verificación"
    CLOSED = "closed", "Cerrada"


class Vulnerability(models.Model):
    """
    Un hallazgo normalizado, sin importar si llegó de OpenVAS, Wazuh
    o Kaspersky. Los campos cvss/epss alimentan el cálculo de
    prioridad; ai_* guarda lo último que devolvió Qwen para ese hallazgo.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="vulnerabilities")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="vulnerabilities")
    source = models.ForeignKey(VulnerabilitySource, on_delete=models.PROTECT, related_name="findings")
    external_id = models.CharField(
        max_length=100, blank=True, help_text="ID del hallazgo en el sistema de origen, para deduplicar en cada sync."
    )
    cve = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    severity = models.CharField(max_length=10, choices=Severity.choices)
    cvss_score = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    epss_score = models.DecimalField(
        max_digits=4, decimal_places=3, null=True, blank=True, help_text="Probabilidad de explotación (0 a 1)."
    )
    priority_score = models.PositiveSmallIntegerField(
        default=0, help_text="Puntaje 0-100 calculado por la IA combinando CVSS, EPSS y criticidad del activo."
    )

    status = models.CharField(max_length=20, choices=VulnerabilityStatus.choices, default=VulnerabilityStatus.OPEN)
    controls = models.ManyToManyField(Control, related_name="vulnerabilities", blank=True)
    due_date = models.DateField(null=True, blank=True)

    ai_summary = models.TextField(blank=True, help_text="Resumen de riesgo en lenguaje llano, generado por Qwen.")
    ai_remediation_steps = models.JSONField(default=list, blank=True)
    ai_rollback_risk = models.TextField(blank=True)
    ai_analyzed_at = models.DateTimeField(null=True, blank=True)

    first_detected_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-priority_score"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "severity"]),
        ]

    def __str__(self):
        return f"{self.cve or self.title} · {self.asset.hostname}"

    @property
    def is_overdue(self):
        from django.utils import timezone

        return bool(self.due_date and self.status != VulnerabilityStatus.CLOSED and self.due_date < timezone.now().date())
