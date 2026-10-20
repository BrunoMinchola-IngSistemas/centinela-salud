import hashlib
import json
import os
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from evidence.models import Evidence, EvidenceType
from vulnerabilities.models import VulnerabilityStatus

from .models import PlanStatus, RemediationPlan, VerificationAttempt
from .serializers import RemediationPlanSerializer

DUE_DAYS_BY_SEVERITY = {"critical": 7, "high": 30, "medium": 60, "low": 90}
EVIDENCE_S3_BUCKET = os.getenv("EVIDENCE_S3_BUCKET", "centinela-salud-evidencias")


def _parse_bool(value):
    """
    bool("false") es True en Python, así que no se puede castear
    directamente un valor que venga de un formulario o querystring
    (donde todo llega como texto). Acepta el bool nativo que manda
    axios/JSON y también las variantes de texto más comunes; devuelve
    None si no se puede interpretar, para que el caller lo trate como
    "no vino el campo".
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip().lower() in ("true", "1", "yes", "si", "sí"):
            return True
        if value.strip().lower() in ("false", "0", "no"):
            return False
    return None


class RemediationPlanViewSet(viewsets.ModelViewSet):
    queryset = RemediationPlan.objects.select_related("vulnerability", "vulnerability__asset").prefetch_related(
        "verification_attempts"
    )
    serializer_class = RemediationPlanSerializer
    filterset_fields = ["status"]

    def get_queryset(self):
        profile = getattr(self.request.user, "profile", None)
        if profile is None:
            return super().get_queryset().none()
        return super().get_queryset().filter(vulnerability__organization=profile.organization)

    def perform_create(self, serializer):
        """
        Si no se indica un plazo, lo calcula a partir de la severidad
        (crítica 7 días, alta 30, media 60, baja 90 - igual que la
        política descrita en el módulo de Administración) y marca la
        vulnerabilidad como 'en plan'.
        """
        vulnerability = serializer.validated_data["vulnerability"]
        due_date = serializer.validated_data.get("due_date") or (
            date.today() + timedelta(days=DUE_DAYS_BY_SEVERITY.get(vulnerability.severity, 30))
        )
        plan = serializer.save(due_date=due_date)
        vulnerability.status = VulnerabilityStatus.IN_PLAN
        vulnerability.save(update_fields=["status"])
        return plan

    @action(detail=True, methods=["patch"], url_path="advance")
    def advance(self, request, pk=None):
        """Mueve la tarjeta en el tablero: pendiente -> en curso -> en verificación."""
        plan = self.get_object()
        next_status = {
            PlanStatus.PENDING: PlanStatus.IN_PROGRESS,
            PlanStatus.IN_PROGRESS: PlanStatus.IN_VERIFICATION,
        }.get(plan.status)
        if not next_status:
            raise serializers.ValidationError("Este plan ya no se puede avanzar manualmente; usa /verify.")
        plan.status = next_status
        plan.save(update_fields=["status"])
        if next_status == PlanStatus.IN_VERIFICATION:
            plan.vulnerability.status = VulnerabilityStatus.IN_VERIFICATION
            plan.vulnerability.save(update_fields=["status"])
        return Response(RemediationPlanSerializer(plan).data)

    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        """
        Registra el resultado de un reescaneo. El llamador indica
        'vulnerability_still_present': en un flujo totalmente
        automatizado esto lo decide integrations.openvas/wazuh
        comparando el hallazgo contra el último reporte; aquí se deja
        explícito en el payload para que un analista también pueda
        confirmarlo a mano tras revisar el reescaneo.

        Si ya no está presente: cierra el plan y la vulnerabilidad, y
        genera un registro de Evidence con su huella SHA-256.
        """
        plan = self.get_object()
        still_present = _parse_bool(request.data.get("vulnerability_still_present"))
        if still_present is None:
            raise serializers.ValidationError("Falta 'vulnerability_still_present' (true/false).")

        attempt = VerificationAttempt.objects.create(
            plan=plan,
            requested_by=request.data.get("requested_by", ""),
            vulnerability_still_present=still_present,
            scan_reference=request.data.get("scan_reference", ""),
        )

        vulnerability = plan.vulnerability
        if not attempt.vulnerability_still_present:
            plan.status = PlanStatus.CLOSED
            plan.save(update_fields=["status"])
            vulnerability.status = VulnerabilityStatus.CLOSED
            vulnerability.closed_at = timezone.now()
            vulnerability.save(update_fields=["status", "closed_at"])

            payload = {
                "plan_id": plan.id,
                "vulnerability": vulnerability.cve or str(vulnerability.id),
                "asset": vulnerability.asset.hostname,
                "verified_at": timezone.now().isoformat(),
                "scan_reference": attempt.scan_reference,
            }
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            Evidence.objects.create(
                organization=vulnerability.organization,
                name=f"Reescaneo {vulnerability.source.get_source_type_display()} · {vulnerability.asset.hostname}",
                evidence_type=EvidenceType.SCAN_REPORT,
                vulnerability=vulnerability,
                plan=plan,
                s3_bucket=EVIDENCE_S3_BUCKET,
                s3_key=f"evidence/{vulnerability.organization_id}/{plan.id}/{attempt.id}.json",
                sha256_hash=digest,
                source_system=vulnerability.source.get_source_type_display(),
                created_by=request.data.get("requested_by", ""),
            )
        else:
            plan.status = PlanStatus.IN_PROGRESS
            plan.save(update_fields=["status"])
            vulnerability.status = VulnerabilityStatus.IN_PLAN
            vulnerability.save(update_fields=["status"])

        return Response(RemediationPlanSerializer(plan).data)
