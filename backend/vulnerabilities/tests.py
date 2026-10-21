from unittest.mock import patch

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Organization
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality
from integrations.qwen import VulnerabilityAnalysis

from .models import Severity, SourceType, Vulnerability, VulnerabilitySource


class OrganizationIsolationTests(APITestCase):
    """
    El punto más delicado de un sistema multi-clínica: que la PyME A
    nunca vea ni pueda tocar los datos de la PyME B. Cada caso crea
    dos organizaciones completas y verifica que cada usuario solo ve
    la suya, tanto en el listado como al intentar leer por id directo.
    """

    def setUp(self):
        self.org_a = Organization.objects.create(name="Clínica A")
        self.org_b = Organization.objects.create(name="Clínica B")

        self.user_a = User.objects.create_user("analista_a", password="x")
        Profile.objects.create(user=self.user_a, organization=self.org_a)

        self.user_b = User.objects.create_user("analista_b", password="x")
        Profile.objects.create(user=self.user_b, organization=self.org_b)

        self.asset_a = Asset.objects.create(
            organization=self.org_a, hostname="srv-a", asset_type=AssetType.SERVER, criticality=Criticality.HIGH
        )
        source_a = VulnerabilitySource.objects.create(
            organization=self.org_a, source_type=SourceType.OPENVAS, name="GVM A"
        )
        self.vuln_a = Vulnerability.objects.create(
            organization=self.org_a,
            asset=self.asset_a,
            source=source_a,
            external_id="a-1",
            title="Hallazgo de la clínica A",
            severity=Severity.HIGH,
        )

    def test_el_usuario_b_no_ve_el_hallazgo_de_la_clinica_a_en_el_listado(self):
        self.client.force_authenticate(self.user_b)
        resp = self.client.get(reverse("vulnerability-list"))

        self.assertEqual(resp.status_code, 200)
        ids = [v["id"] for v in resp.data["results"]]
        self.assertNotIn(str(self.vuln_a.id), ids)

    def test_el_usuario_b_no_puede_leer_el_hallazgo_de_la_clinica_a_por_id(self):
        self.client.force_authenticate(self.user_b)
        resp = self.client.get(reverse("vulnerability-detail", kwargs={"pk": self.vuln_a.id}))

        self.assertEqual(resp.status_code, 404)

    def test_el_usuario_a_si_ve_su_propio_hallazgo(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.get(reverse("vulnerability-detail", kwargs={"pk": self.vuln_a.id}))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], str(self.vuln_a.id))

    def test_sin_perfil_de_organizacion_la_api_rechaza_en_vez_de_mostrar_todo(self):
        user_sin_perfil = User.objects.create_user("huerfano", password="x")
        self.client.force_authenticate(user_sin_perfil)

        resp = self.client.get(reverse("vulnerability-list"))

        self.assertEqual(resp.status_code, 403)


class VulnerabilityValidationTests(APITestCase):
    """
    El modelo no tenía validadores de rango para CVSS/EPSS (un
    DecimalField solo limita cuántos dígitos acepta, no el rango), así
    que un POST/PATCH podía guardar un CVSS de 50 o un EPSS de 3 sin
    que nada se quejara. Se agregaron validate_cvss_score/
    validate_epss_score en el serializer.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.user = User.objects.create_user("analista", password="x")
        Profile.objects.create(user=self.user, organization=self.org)
        self.asset = Asset.objects.create(
            organization=self.org, hostname="srv-test", asset_type=AssetType.SERVER, criticality=Criticality.HIGH
        )
        self.source = VulnerabilitySource.objects.create(
            organization=self.org, source_type=SourceType.OPENVAS, name="GVM"
        )
        self.client.force_authenticate(self.user)

    def _payload(self, **overrides):
        payload = {
            "cve": "CVE-2024-0001",
            "title": "Hallazgo de prueba",
            "severity": Severity.HIGH,
            "asset": str(self.asset.id),
            "source": self.source.id,
        }
        payload.update(overrides)
        return payload

    def test_cvss_fuera_de_0_10_es_rechazado(self):
        resp = self.client.post(reverse("vulnerability-list"), self._payload(cvss_score=50))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cvss_score", resp.data)

    def test_cvss_negativo_es_rechazado(self):
        resp = self.client.post(reverse("vulnerability-list"), self._payload(cvss_score=-1))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cvss_score", resp.data)

    def test_cvss_valido_se_acepta(self):
        resp = self.client.post(reverse("vulnerability-list"), self._payload(cvss_score=9.8))
        self.assertEqual(resp.status_code, 201)

    def test_epss_fuera_de_0_1_es_rechazado(self):
        resp = self.client.post(reverse("vulnerability-list"), self._payload(epss_score=3))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("epss_score", resp.data)


class AIEndpointsTests(APITestCase):
    """
    Los endpoints de IA (analyze, explain_simple, clinical_impact)
    llaman a integrations.qwen, que a su vez hace una petición HTTP a
    un servidor Qwen local que no existe en el entorno de pruebas (ni
    en CI). Se mockea integrations.qwen para probar que la vista
    procesa y guarda la respuesta correctamente, sin depender de que
    Qwen esté corriendo.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba IA")
        self.user = User.objects.create_user("analista_ia", password="x")
        Profile.objects.create(user=self.user, organization=self.org)
        self.asset = Asset.objects.create(
            organization=self.org, hostname="srv-ia", asset_type=AssetType.SERVER, criticality=Criticality.CRITICAL
        )
        self.source = VulnerabilitySource.objects.create(
            organization=self.org, source_type=SourceType.OPENVAS, name="GVM"
        )
        self.vuln = Vulnerability.objects.create(
            organization=self.org,
            asset=self.asset,
            source=self.source,
            external_id="ia-1",
            title="Hallazgo para IA",
            severity=Severity.CRITICAL,
            cvss_score=9.1,
        )
        self.client.force_authenticate(self.user)

    @patch("vulnerabilities.views.qwen.analyze_vulnerability")
    def test_analyze_guarda_el_resumen_y_los_pasos_de_qwen(self, mock_analyze):
        mock_analyze.return_value = VulnerabilityAnalysis(
            summary="Resumen simulado del riesgo.",
            steps=["Paso 1", "Paso 2"],
            rollback_risk="bajo",
            priority_score=87,
        )

        resp = self.client.post(reverse("vulnerability-analyze", kwargs={"pk": self.vuln.id}))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["ai_summary"], "Resumen simulado del riesgo.")
        self.assertEqual(resp.data["ai_remediation_steps"], ["Paso 1", "Paso 2"])
        self.vuln.refresh_from_db()
        self.assertEqual(self.vuln.priority_score, 87)
        self.assertIsNotNone(self.vuln.ai_analyzed_at)

    @patch("vulnerabilities.views.qwen.simplify_explanation")
    def test_explain_simple_devuelve_el_texto_de_qwen(self, mock_explain):
        mock_explain.return_value = "En palabras simples: esto es grave."

        resp = self.client.post(reverse("vulnerability-explain-simple", kwargs={"pk": self.vuln.id}))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["text"], "En palabras simples: esto es grave.")

    @patch("vulnerabilities.views.qwen.clinical_impact")
    def test_clinical_impact_devuelve_el_texto_de_qwen(self, mock_impact):
        mock_impact.return_value = "Podría afectar el monitoreo de pacientes."

        resp = self.client.post(reverse("vulnerability-clinical-impact", kwargs={"pk": self.vuln.id}))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["text"], "Podría afectar el monitoreo de pacientes.")


class PrioridadContextualIntegracionTests(APITestCase):
    """La prioridad R1-R5 se guarda sola y se recalcula si cambia el activo."""

    def setUp(self):
        self.org = Organization.objects.create(name="Clínica")
        self.asset = Asset.objects.create(
            organization=self.org, hostname="portal", asset_type=AssetType.APPLICATION,
            criticality=Criticality.HIGH, exposure="interna",
        )
        source = VulnerabilitySource.objects.create(organization=self.org, source_type=SourceType.OPENVAS, name="GVM")
        self.vuln = Vulnerability.objects.create(
            organization=self.org, asset=self.asset, source=source, external_id="x", title="t",
            severity=Severity.HIGH, cvss_score=7.5,
        )

    def test_se_calcula_al_crear(self):
        self.assertEqual(self.vuln.contextual_priority, "high")

    def test_cambiar_exposicion_del_activo_recalcula(self):
        self.asset.exposure = "internet"
        self.asset.save()
        self.vuln.refresh_from_db()
        self.assertEqual(self.vuln.contextual_priority, "critical")
        self.assertEqual(self.vuln.priority_rules["reglas"][0]["regla"], "R1")


class EscrituraCruzadaEntreOrganizacionesTests(APITestCase):
    """Un usuario no puede crear planes ni solicitudes sobre datos de otra clínica (sin depender de RLS)."""

    def setUp(self):
        from remediation.models import RemediationPlan

        self.org_a = Organization.objects.create(name="A")
        self.org_b = Organization.objects.create(name="B")
        self.user_a = User.objects.create_user("a", password="x")
        Profile.objects.create(user=self.user_a, organization=self.org_a)
        asset_b = Asset.objects.create(organization=self.org_b, hostname="b", asset_type=AssetType.SERVER)
        src_b = VulnerabilitySource.objects.create(organization=self.org_b, source_type=SourceType.MANUAL, name="m")
        self.vuln_b = Vulnerability.objects.create(organization=self.org_b, asset=asset_b, source=src_b, title="b", severity=Severity.HIGH)
        vuln_b2 = Vulnerability.objects.create(organization=self.org_b, asset=asset_b, source=src_b, external_id="2", title="b2", severity=Severity.HIGH)
        from django.utils import timezone
        self.plan_b = RemediationPlan.objects.create(vulnerability=vuln_b2, owner_name="x", due_date=timezone.now().date())

    def test_no_crea_plan_sobre_hallazgo_ajeno(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(reverse("remediation-plan-list"), {"vulnerability": self.vuln_b.id, "owner_name": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_no_crea_solicitud_sobre_plan_ajeno(self):
        from django.utils import timezone
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(reverse("solicitud-aprobacion-list"), {
            "plan": self.plan_b.id, "tipo_accion": "otro", "riesgo_de_no_actuar": "r", "efecto_esperado": "e",
            "plazo": timezone.now(),
        })
        self.assertEqual(resp.status_code, 400)

    def test_no_crea_activo_ni_hallazgo_apuntando_a_activo_ajeno(self):
        self.client.force_authenticate(self.user_a)
        resp = self.client.post(reverse("vulnerability-list"), {
            "title": "t", "severity": "high", "asset": self.vuln_b.asset_id, "source": self.vuln_b.source_id,
        })
        self.assertEqual(resp.status_code, 400)
