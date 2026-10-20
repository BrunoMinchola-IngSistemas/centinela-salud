from datetime import date

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Organization
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource, VulnerabilityStatus

from .models import PlanStatus, RemediationPlan


class RemediationFlowTests(APITestCase):
    """
    Cubre el ciclo completo que importa para la tesis: una
    vulnerabilidad abierta pasa a tener un plan, el plan se puede
    verificar, y verificar negativamente (ya no está presente) cierra
    tanto el plan como la vulnerabilidad y genera una evidencia con
    huella SHA-256. Verificar positivamente (sigue presente) la
    regresa a "en plan" sin cerrar nada.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.user = User.objects.create_user("analista", password="x")
        Profile.objects.create(user=self.user, organization=self.org)
        self.client.force_authenticate(self.user)

        self.asset = Asset.objects.create(
            organization=self.org,
            hostname="srv-test-01",
            asset_type=AssetType.SERVER,
            criticality=Criticality.CRITICAL,
        )
        self.source = VulnerabilitySource.objects.create(
            organization=self.org, source_type=SourceType.OPENVAS, name="GVM de prueba"
        )
        self.vuln = Vulnerability.objects.create(
            organization=self.org,
            asset=self.asset,
            source=self.source,
            external_id="ext-1",
            title="Vulnerabilidad de prueba",
            severity=Severity.CRITICAL,
            cvss_score=9.8,
        )

    def test_crear_plan_marca_vulnerabilidad_en_plan(self):
        url = reverse("remediation-plan-list")
        resp = self.client.post(url, {"vulnerability": str(self.vuln.id), "owner_name": "Responsable"})
        self.assertEqual(resp.status_code, 201, resp.content)

        self.vuln.refresh_from_db()
        self.assertEqual(self.vuln.status, VulnerabilityStatus.IN_PLAN)
        self.assertIsNotNone(resp.data["due_date"])  # calculado por severidad al no enviarlo

    def test_verificar_que_sigue_presente_no_cierra_nada(self):
        plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="Responsable", due_date=date.today())
        url = reverse("remediation-plan-verify", kwargs={"pk": plan.pk})

        resp = self.client.post(url, {"vulnerability_still_present": True, "requested_by": "Analista"})

        self.assertEqual(resp.status_code, 200, resp.content)
        plan.refresh_from_db()
        self.vuln.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.IN_PROGRESS)
        self.assertEqual(self.vuln.status, VulnerabilityStatus.IN_PLAN)
        self.assertFalse(self.vuln.evidence_items.exists())

    def test_verificar_que_ya_no_esta_presente_cierra_y_genera_evidencia(self):
        plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="Responsable", due_date=date.today())
        url = reverse("remediation-plan-verify", kwargs={"pk": plan.pk})

        resp = self.client.post(
            url, {"vulnerability_still_present": False, "requested_by": "Analista", "scan_reference": "scan-1"}
        )

        self.assertEqual(resp.status_code, 200, resp.content)
        plan.refresh_from_db()
        self.vuln.refresh_from_db()
        self.assertEqual(plan.status, PlanStatus.CLOSED)
        self.assertEqual(self.vuln.status, VulnerabilityStatus.CLOSED)
        self.assertIsNotNone(self.vuln.closed_at)

        evidence = self.vuln.evidence_items.first()
        self.assertIsNotNone(evidence)
        self.assertEqual(len(evidence.sha256_hash), 64)

    def test_no_se_puede_crear_dos_planes_para_la_misma_vulnerabilidad(self):
        RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="Responsable", due_date=date.today())
        url = reverse("remediation-plan-list")

        resp = self.client.post(url, {"vulnerability": str(self.vuln.id), "owner_name": "Otro responsable"})

        self.assertEqual(resp.status_code, 400)
