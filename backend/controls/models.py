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
    iso_code = models.CharField(
        "Código ISO/IEC 27001:2022", max_length=10, blank=True, help_text="Código del Anexo A, p. ej. '8.8'."
    )
    theme = models.CharField(
        "Tema del Anexo A",
        max_length=20,
        blank=True,
        choices=[
            ("organizacional", "Organizacionales"),
            ("personas", "Personas"),
            ("fisico", "Físicos"),
            ("tecnologico", "Tecnológicos"),
        ],
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    health_rationale = models.TextField(
        "Por qué importa en salud", blank=True, help_text="Referencia temática a ISO 27799 / contexto clínico."
    )
    baseline_score = models.PositiveSmallIntegerField(
        default=70, help_text="Puntaje base de cumplimiento (0-100) antes de ajustar por hallazgos abiertos/cerrados."
    )

    class Meta:
        ordering = ["iso_code", "name"]

    def __str__(self):
        return f"{self.iso_code} {self.name}".strip()


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
