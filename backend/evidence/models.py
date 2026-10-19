import uuid

from django.db import models

from accounts.models import Organization
from remediation.models import RemediationPlan
from vulnerabilities.models import Vulnerability


class EvidenceType(models.TextChoices):
    SCAN_REPORT = "scan_report", "Informe de escaneo"
    CONFIGURATION = "configuration", "Configuración"
    SIGNED_RECORD = "signed_record", "Acta firmada"
    OTHER = "other", "Otro"


class Evidence(models.Model):
    """
    Un archivo probatorio (informe de reescaneo, captura de config,
    acta firmada) guardado en S3 y referenciado aquí junto a su huella
    SHA-256, para que el registro en PostgreSQL sea la fuente de verdad
    de integridad aunque alguien manipule el archivo en S3.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="evidence_items")
    name = models.CharField(max_length=255)
    evidence_type = models.CharField(max_length=20, choices=EvidenceType.choices)

    vulnerability = models.ForeignKey(
        Vulnerability, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidence_items"
    )
    plan = models.ForeignKey(
        RemediationPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name="evidence_items"
    )

    s3_bucket = models.CharField(max_length=150)
    s3_key = models.CharField(max_length=500)
    sha256_hash = models.CharField(max_length=64)
    source_system = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["s3_bucket", "s3_key"], name="uniq_evidence_object")]

    def __str__(self):
        return self.name
