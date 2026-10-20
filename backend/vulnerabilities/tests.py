from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Organization
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality

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
