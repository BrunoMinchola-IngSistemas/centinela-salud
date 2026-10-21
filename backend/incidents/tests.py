from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Organization
from accounts.models import User as Profile
from governance.models import RegistroAuditoria

from .models import IncidenteReportado


class IncidenteReportadoTests(APITestCase):
    """HU30: reportar un incidente con 3 campos (qué, dónde, cuándo)."""

    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.user = User.objects.create_user("personal", password="x")
        Profile.objects.create(user=self.user, organization=self.org)

    def test_reportar_incidente_con_los_3_campos_basta(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("incidente-list"),
            {
                "descripcion": "Encontré una laptop desbloqueada con el historial de un paciente abierto.",
                "lugar": "Consultorio 3",
                "ocurrido_en": timezone.now(),
            },
        )

        self.assertEqual(resp.status_code, 201)
        incidente = IncidenteReportado.objects.get(id=resp.data["id"])
        self.assertEqual(incidente.organization, self.org)
        self.assertEqual(incidente.reportado_por, "personal")
        self.assertTrue(RegistroAuditoria.objects.filter(accion="incidente_reportado").exists())

    def test_otra_organizacion_no_ve_el_incidente(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("incidente-list"),
            {
                "descripcion": "Prueba",
                "lugar": "Sala 1",
                "ocurrido_en": timezone.now(),
            },
        )
        incidente_id = resp.data["id"]

        otra_org = Organization.objects.create(name="Otra clínica")
        otro_user = User.objects.create_user("otro", password="x")
        Profile.objects.create(user=otro_user, organization=otra_org)

        self.client.force_authenticate(otro_user)
        resp = self.client.get(reverse("incidente-detail", kwargs={"pk": incidente_id}))
        self.assertEqual(resp.status_code, 404)
