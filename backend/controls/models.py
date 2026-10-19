from django.db import models

from accounts.models import Organization


class Framework(models.TextChoices):
    """Marcos normativos contra los que se mapean los controles."""

    ISO27001 = "iso27001", "ISO 27001:2022"
    HIPAA = "hipaa", "HIPAA Security Rule"
    CIS = "cis", "CIS Controls v8"


class Control(models.Model):
    """
    Un control de seguridad (p. ej. 'Gestión de vulnerabilidades técnicas').
    Se referencia desde varios marcos a la vez mediante ControlMapping,
    porque el mismo control suele tener un código distinto en cada marco.
    """

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="controls")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    baseline_score = models.PositiveSmallIntegerField(
        default=70, help_text="Puntaje base de cumplimiento (0-100) antes de ajustar por hallazgos abiertos/cerrados."
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ControlMapping(models.Model):
    """Código de un control dentro de un marco normativo específico."""

    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="mappings")
    framework = models.CharField(max_length=20, choices=Framework.choices)
    code = models.CharField(max_length=30)

    class Meta:
        unique_together = ("control", "framework")

    def __str__(self):
        return f"{self.get_framework_display()} {self.code}"


class ComplianceAssessment(models.Model):
    """
    Resultado de una evaluación de un control en un momento dado.
    Puede ser generada por IA (Qwen) o registrada manualmente por un auditor.
    """

    control = models.ForeignKey(Control, on_delete=models.CASCADE, related_name="assessments")
    score = models.PositiveSmallIntegerField()
    generated_by_ai = models.BooleanField(default=False)
    recommendation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-created_at"]
