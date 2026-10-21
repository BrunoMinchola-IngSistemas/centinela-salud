from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Organization
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality
from remediation.models import RemediationPlan
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource

from .models import (
    EstadoSolicitud,
    NivelAutonomia,
    PoliticaAutonomia,
    RegistroAuditoria,
    SolicitudAprobacion,
    TipoAccion,
)


class GovernanceTestsBase(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.user = User.objects.create_user("analista", password="x")
        Profile.objects.create(user=self.user, organization=self.org)

        self.asset = Asset.objects.create(
            organization=self.org, hostname="srv-1", asset_type=AssetType.SERVER, criticality=Criticality.HIGH
        )
        source = VulnerabilitySource.objects.create(
            organization=self.org, source_type=SourceType.OPENVAS, name="GVM"
        )
        self.vuln = Vulnerability.objects.create(
            organization=self.org,
            asset=self.asset,
            source=source,
            external_id="v-1",
            title="Hallazgo de prueba",
            severity=Severity.HIGH,
        )
        self.plan = RemediationPlan.objects.create(
            vulnerability=self.vuln, owner_name="TI", due_date=timezone.now().date()
        )


class PoliticaAutonomiaTests(GovernanceTestsBase):
    def test_crear_y_listar_politica_de_la_propia_organizacion(self):
        self.client.force_authenticate(self.user)
        resp = self.client.post(
            reverse("politica-autonomia-list"),
            {"tipo_accion": TipoAccion.APLICAR_PARCHE, "nivel": NivelAutonomia.ASISTIDO},
        )
        self.assertEqual(resp.status_code, 201)

        otra_org = Organization.objects.create(name="Otra clínica")
        PoliticaAutonomia.objects.create(
            organization=otra_org, tipo_accion=TipoAccion.OTRO, nivel=NivelAutonomia.ASISTIDO
        )

        resp = self.client.get(reverse("politica-autonomia-list"))
        self.assertEqual(len(resp.data["results"]), 1)


class SolicitudAprobacionTests(GovernanceTestsBase):
    def _crear_solicitud(self):
        return self.client.post(
            reverse("solicitud-aprobacion-list"),
            {
                "plan": self.plan.id,
                "tipo_accion": TipoAccion.AISLAR_SERVIDOR,
                "riesgo_de_no_actuar": "El servidor sigue expuesto a explotación activa.",
                "efecto_esperado": "El servidor queda aislado de la red hasta aplicar el parche.",
                "plazo": timezone.now() + timezone.timedelta(hours=4),
            },
        )

    def test_crear_solicitud_registra_auditoria(self):
        self.client.force_authenticate(self.user)
        resp = self._crear_solicitud()

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(SolicitudAprobacion.objects.count(), 1)
        self.assertEqual(RegistroAuditoria.objects.filter(accion="solicitud_creada").count(), 1)

    def test_aprobar_solicitud_cambia_estado_y_registra_quien_decidio(self):
        self.client.force_authenticate(self.user)
        resp = self._crear_solicitud()
        solicitud_id = resp.data["id"]

        resp = self.client.post(
            reverse("solicitud-aprobacion-aprobar", kwargs={"pk": solicitud_id}),
            {"comentario": "Aprobado por riesgo alto."},
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["estado"], EstadoSolicitud.APROBADA)
        self.assertEqual(resp.data["decidido_por"], "analista")
        self.assertTrue(RegistroAuditoria.objects.filter(accion="solicitud_aprobada").exists())

    def test_rechazar_solicitud(self):
        self.client.force_authenticate(self.user)
        resp = self._crear_solicitud()
        solicitud_id = resp.data["id"]

        resp = self.client.post(reverse("solicitud-aprobacion-rechazar", kwargs={"pk": solicitud_id}))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["estado"], EstadoSolicitud.RECHAZADA)

    def test_otra_organizacion_no_ve_la_solicitud(self):
        self.client.force_authenticate(self.user)
        resp = self._crear_solicitud()
        solicitud_id = resp.data["id"]

        otra_org = Organization.objects.create(name="Otra clínica")
        otro_user = User.objects.create_user("otro", password="x")
        Profile.objects.create(user=otro_user, organization=otra_org)

        self.client.force_authenticate(otro_user)
        resp = self.client.get(reverse("solicitud-aprobacion-detail", kwargs={"pk": solicitud_id}))
        self.assertEqual(resp.status_code, 404)


class RegistroAuditoriaTests(GovernanceTestsBase):
    def test_log_no_expone_update_ni_destroy(self):
        """HU27/RNF-05: el log es de solo inserción, también a nivel de API."""
        registro = RegistroAuditoria.objects.create(
            organization=self.org,
            actor="agente",
            accion="prueba",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="vulnerability",
            objeto_id=str(self.vuln.id),
        )
        self.client.force_authenticate(self.user)

        resp = self.client.patch(reverse("registro-auditoria-detail", kwargs={"pk": registro.id}), {"actor": "otro"})
        self.assertEqual(resp.status_code, 405)

        resp = self.client.delete(reverse("registro-auditoria-detail", kwargs={"pk": registro.id}))
        self.assertEqual(resp.status_code, 405)

    def test_modelo_rechaza_un_segundo_save_sobre_el_mismo_registro(self):
        registro = RegistroAuditoria.objects.create(
            organization=self.org,
            actor="agente",
            accion="prueba",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="vulnerability",
            objeto_id=str(self.vuln.id),
        )
        registro.accion = "modificado"
        with self.assertRaises(ValueError):
            registro.save()
