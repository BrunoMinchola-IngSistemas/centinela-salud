import hashlib
import json
import os
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.models import Role
from accounts.models import User as Perfil
from evidence.models import Evidence, EvidenceType
from governance.audit import registrar
from governance.models import NivelAutonomia, TipoAccion
from informes.exportar import exportar_tabla
from vulnerabilities.models import Vulnerability, VulnerabilityStatus

from .models import PlanStatus, RemediationPlan, VerificationAttempt
from .serializers import RemediationPlanSerializer

DUE_DAYS_BY_SEVERITY = {"critical": 7, "high": 30, "medium": 60, "low": 90}
ORDEN_PRIORIDAD = ["critical", "high", "medium", "low"]
ESTADO_TEXTO = {"pending": "Pendiente", "in_progress": "En curso", "in_verification": "En verificación", "closed": "Cerrado"}
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
    modulo = "remediacion"

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
        registrar(
            organization=vulnerability.organization,
            actor=self.request.user.username,
            accion="plan_creado",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="vulnerability",
            objeto_id=vulnerability.id,
            detalle={"titulo": vulnerability.title, "prioridad": vulnerability.contextual_priority, "plazo": str(due_date)},
        )
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
        registrar(
            organization=plan.vulnerability.organization,
            actor=request.user.username,
            accion="plan_avanzado",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="remediation_plan",
            objeto_id=plan.id,
            detalle={"a": next_status, "hallazgo": plan.vulnerability.title},
        )
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
        registrar(
            organization=vulnerability.organization,
            actor=request.user.username,
            accion="verificacion_cerrada" if not still_present else "verificacion_fallida",
            modalidad=NivelAutonomia.ASISTIDO,
            objeto_tipo="vulnerability",
            objeto_id=vulnerability.id,
            detalle={"hallazgo": vulnerability.title, "sigue_presente": still_present, "reescaneo": attempt.scan_reference},
        )
        if not attempt.vulnerability_still_present:
            plan.status = PlanStatus.CLOSED
            plan.save(update_fields=["status"])
            vulnerability.status = VulnerabilityStatus.CLOSED
            vulnerability.closed_at = timezone.now()
            vulnerability.save(update_fields=["status", "closed_at"])

            payload = {
                "plan_id": plan.id,
                "vulnerability": vulnerability.cve or str(vulnerability.id),
                "asset": vulnerability.asset.hostname if vulnerability.asset else "",
                "verified_at": timezone.now().isoformat(),
                "scan_reference": attempt.scan_reference,
            }
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
            Evidence.objects.create(
                organization=vulnerability.organization,
                name=f"Reescaneo {vulnerability.source.get_source_type_display()} · "
                f"{vulnerability.asset.hostname if vulnerability.asset else 'sin activo'}",
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


    # ------------------------------------------------------------- HU17

    @action(detail=False, methods=["post"])
    def generar(self, request):
        """
        HU17: el agente arma el plan de remediación para los hallazgos
        priorizados que aún no tienen plan: una acción por hallazgo con
        responsable (el Responsable de TI disponible), plazo según la
        prioridad y estado "pendiente". Si no hay un responsable
        disponible, la acción queda como "responsable pendiente de
        asignación". Al crear cada plan, el agente notifica a TI de forma
        autónoma (acción de la lista blanca, HU18).
        """
        from governance.agente import proponer_accion

        profile = request.user.profile
        if profile.role not in {Role.ADMIN, Role.COMPLIANCE, Role.IT_OWNER, Role.ANALYST}:
            raise serializers.ValidationError("Tu rol no puede generar planes de remediación.")
        minima = request.data.get("prioridad_minima", "low")
        if minima not in ORDEN_PRIORIDAD:
            raise serializers.ValidationError({"prioridad_minima": "Usa critical, high, medium o low."})
        aceptadas = ORDEN_PRIORIDAD[: ORDEN_PRIORIDAD.index(minima) + 1]

        responsable = (
            Perfil.objects.select_related("user")
            .filter(organization=profile.organization, role=Role.IT_OWNER, user__is_active=True)
            .order_by("user__username")
            .first()
        )
        candidatas = (
            Vulnerability.objects.filter(organization=profile.organization, plan__isnull=True)
            .exclude(status=VulnerabilityStatus.CLOSED)
            .select_related("asset")
        )
        creados = []
        for v in sorted(candidatas, key=lambda x: (ORDEN_PRIORIDAD.index(x.contextual_priority) if x.contextual_priority in ORDEN_PRIORIDAD else 1, -x.priority_score)):
            nivel = v.contextual_priority or v.severity
            if nivel not in aceptadas and v.contextual_priority:
                continue
            plan = RemediationPlan.objects.create(
                vulnerability=v,
                owner_name=responsable.user.get_full_name() or responsable.user.username if responsable else "",
                owner_email=responsable.user.email if responsable else "",
                due_date=date.today() + timedelta(days=DUE_DAYS_BY_SEVERITY.get(nivel, 30)),
                notes="Plan generado por el agente a partir de la prioridad contextual.",
                generado_por_agente=True,
            )
            v.status = VulnerabilityStatus.IN_PLAN
            v.save(update_fields=["status"])
            registrar(
                organization=v.organization,
                actor="agente",
                accion="plan_generado",
                modalidad=NivelAutonomia.AUTONOMO,
                objeto_tipo="vulnerability",
                objeto_id=v.id,
                detalle={"pedido_por": request.user.username, "titulo": v.title, "responsable": plan.owner_name or "pendiente",
                         "plazo": str(plan.due_date)},
            )
            proponer_accion(plan, TipoAccion.NOTIFICAR, propuesta_por="agente", detalle="Aviso del plan generado.")
            creados.append(plan)
        return Response(
            {
                "creados": len(creados),
                "responsable_disponible": bool(responsable),
                "planes": RemediationPlanSerializer(creados, many=True, context=self.get_serializer_context()).data,
            },
            status=201,
        )

    @action(detail=False, methods=["get"])
    def exportar(self, request):
        """HU17: plan de remediación exportable (?formato=pdf|xlsx|csv)."""
        planes = self.filter_queryset(self.get_queryset())
        columnas = ["Acción", "Activo", "Prioridad", "Responsable", "Plazo", "Estado", "Vencido"]
        filas = [
            [
                f"Corregir: {p.vulnerability.title}" + (f" ({p.vulnerability.cve})" if p.vulnerability.cve else ""),
                p.vulnerability.asset.hostname if p.vulnerability.asset else "Pendiente de asociación",
                {"critical": "Crítica", "high": "Alta", "medium": "Media", "low": "Baja"}.get(p.vulnerability.contextual_priority, "-"),
                p.owner_name or "Responsable pendiente de asignación",
                p.due_date.strftime("%d/%m/%Y"),
                ESTADO_TEXTO.get(p.status, p.status),
                "Sí" if p.status != "closed" and p.due_date < date.today() else "No",
            ]
            for p in planes
        ]
        return exportar_tabla(
            "plan_remediacion", f"Plan de remediación · {request.user.profile.organization.name}", columnas, filas,
            request.query_params.get("formato", "pdf"), anchos=(40, 18, 10, 20, 11, 12, 8),
        )
