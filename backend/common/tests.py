"""
Pruebas de Row-Level Security. Solo corren cuando la base es PostgreSQL
(en SQLite no existe RLS y se saltan). Usan autenticación real por token
(no force_authenticate) para pasar por el mismo camino que la consola.
"""

import unittest

from django.contrib.auth.models import User
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import Organization, Role
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality
from governance.models import RegistroAuditoria
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource


@unittest.skipUnless(connection.vendor == "postgresql", "RLS solo existe en PostgreSQL")
class RowLevelSecurityTests(APITestCase):
    def _org(self, nombre, usuario, rol=Role.ANALYST):
        org = Organization.objects.create(name=nombre)
        user = User.objects.create_user(usuario, password="x")
        Profile.objects.create(user=user, organization=org, role=rol)
        asset = Asset.objects.create(organization=org, hostname=f"srv-{usuario}", asset_type=AssetType.SERVER, criticality=Criticality.HIGH)
        src = VulnerabilitySource.objects.create(organization=org, source_type=SourceType.MANUAL, name="m")
        vuln = Vulnerability.objects.create(organization=org, asset=asset, source=src, external_id=usuario, title=f"hallazgo {usuario}", severity=Severity.HIGH)
        return org, user, vuln

    def setUp(self):
        self.org_a, self.user_a, self.vuln_a = self._org("A", "ana")
        self.org_b, self.user_b, self.vuln_b = self._org("B", "beto")

    def _login(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=user).key}")

    def test_la_api_corre_con_el_rol_restringido(self):
        self._login(self.user_a)
        resp = self.client.get(reverse("auth-me"))
        self.assertEqual(resp.status_code, 200)
        # Al terminar la petición la conexión vuelve a su rol normal.
        with connection.cursor() as cur:
            cur.execute("SELECT current_user")
            self.assertNotEqual(cur.fetchone()[0], "centinela_app")

    def test_cada_org_ve_solo_lo_suyo_por_api(self):
        self._login(self.user_a)
        ids = [v["id"] for v in self.client.get(reverse("vulnerability-list")).data["results"]]
        self.assertEqual(ids, [str(self.vuln_a.id)])
        resp = self.client.get(reverse("vulnerability-detail", kwargs={"pk": self.vuln_b.id}))
        self.assertEqual(resp.status_code, 404)

    def test_escrituras_normales_funcionan_bajo_rls(self):
        self._login(self.user_a)
        resp = self.client.post(reverse("remediation-plan-list"), {"vulnerability": self.vuln_a.id, "owner_name": "TI"})
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.client.post(
            reverse("incidente-list"), {"descripcion": "x", "lugar": "y", "ocurrido_en": timezone.now()}
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(RegistroAuditoria.objects.filter(organization=self.org_a, accion="plan_creado").exists())

    def test_no_puede_crear_plan_para_hallazgo_de_otra_org(self):
        self._login(self.user_a)
        resp = self.client.post(reverse("remediation-plan-list"), {"vulnerability": self.vuln_b.id, "owner_name": "TI"})
        self.assertEqual(resp.status_code, 400)

    def test_motor_niega_update_en_auditoria(self):
        reg = RegistroAuditoria.objects.create(
            organization=self.org_a, actor="x", accion="y", modalidad="autonomo", objeto_tipo="t", objeto_id="1"
        )
        from django.db import transaction
        from django.db.utils import ProgrammingError

        with self.assertRaises(ProgrammingError):
            with transaction.atomic(), connection.cursor() as cur:
                cur.execute("SET LOCAL ROLE centinela_app")
                cur.execute("SELECT set_config('app.current_org', %s, true)", [str(self.org_a.id)])
                cur.execute("UPDATE governance_registroauditoria SET actor = 'hacker' WHERE id = %s", [reg.id])
