from django.db import models

from vulnerabilities.models import Vulnerability


class PlanStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    IN_PROGRESS = "in_progress", "En curso"
    IN_VERIFICATION = "in_verification", "En verificación"
    CLOSED = "closed", "Cerrado"


class RemediationPlan(models.Model):
    """
    Una tarea de corrección para UNA vulnerabilidad, con responsable y
    plazo. Vive en el tablero kanban del módulo 'Plan de corrección'.
    """

    vulnerability = models.OneToOneField(Vulnerability, on_delete=models.CASCADE, related_name="plan")
    owner_name = models.CharField(max_length=150)
    owner_email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=PlanStatus.choices, default=PlanStatus.PENDING)
    due_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"Plan para {self.vulnerability}"


class VerificationAttempt(models.Model):
    """
    Cada reescaneo lanzado desde el módulo de verificación. Si el
    reescaneo confirma que la vulnerabilidad ya no está presente,
    el servicio que procesa esto cierra el plan y la vulnerabilidad,
    y genera una Evidence (ver app evidence).
    """

    plan = models.ForeignKey(RemediationPlan, on_delete=models.CASCADE, related_name="verification_attempts")
    requested_at = models.DateTimeField(auto_now_add=True)
    requested_by = models.CharField(max_length=150, blank=True)
    vulnerability_still_present = models.BooleanField(null=True, help_text="Null mientras está en curso.")
    scan_reference = models.CharField(max_length=150, blank=True, help_text="ID del escaneo en OpenVAS/Wazuh.")

    class Meta:
        ordering = ["-requested_at"]
