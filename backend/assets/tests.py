from unittest import mock

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Organization, Role
from accounts.models import User as Profile

from . import discovery
from .models import Asset, AssetStatus, AssetType, Criticality, DiscoveryRun, DiscoverySource


class AssetApiTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.user = User.objects.create_user("analista", password="x")
        Profile.objects.create(user=self.user, organization=self.org)
        self.client.force_authenticate(self.user)

    def test_crear_activo_queda_asociado_a_la_organizacion_del_usuario(self):
        resp = self.client.post(
            reverse("asset-list"),
            {
                "hostname": "srv-nuevo",
                "asset_type": AssetType.SERVER,
                "criticality": Criticality.HIGH,
                "stores_phi": True,
            },
        )

        self.assertEqual(resp.status_code, 201, resp.content)
        asset = Asset.objects.get(hostname="srv-nuevo")
        self.assertEqual(asset.organization, self.org)

    def test_no_se_puede_duplicar_el_mismo_hostname_en_la_misma_organizacion(self):
        Asset.objects.create(organization=self.org, hostname="srv-dup", asset_type=AssetType.SERVER)

        resp = self.client.post(reverse("asset-list"), {"hostname": "srv-dup", "asset_type": AssetType.SERVER})

        self.assertEqual(resp.status_code, 400)


class DescubrimientoTests(APITestCase):
    """
    Descubrimiento de activos. Las sondas de red (ping, ARP, DNS) se
    reemplazan por funciones falsas: la prueba verifica la conciliación
    con el inventario, los permisos y el informe, no la red real.
    """

    def setUp(self):
        from governance.models import RegistroAuditoria

        self.RegistroAuditoria = RegistroAuditoria
        self.org = Organization.objects.create(name="Clínica descubrimiento")

        def crear(username, role):
            user = User.objects.create_user(username, password="x")
            Profile.objects.create(user=user, organization=self.org, role=role)
            return user

        self.admin = crear("admin", Role.ADMIN)
        self.ti = crear("ti", Role.IT_OWNER)
        self.analista = crear("analista", Role.ANALYST)
        self.auditor = crear("auditor", Role.AUDITOR)

        # Dos activos ya inventariados en el rango: uno responderá y otro no.
        self.conocido = Asset.objects.create(organization=self.org, hostname="srv-ehr-01", asset_type=AssetType.SERVER, ip_address="10.10.1.11")
        self.apagado = Asset.objects.create(organization=self.org, hostname="srv-viejo", asset_type=AssetType.SERVER, ip_address="10.10.1.99")
        # Y uno fuera del rango, que no debe tocarse.
        self.fuera = Asset.objects.create(organization=self.org, hostname="portal", asset_type=AssetType.APPLICATION, ip_address="10.10.2.8")

    def _sondas_falsas(self):
        vivos = {"10.10.1.11", "10.10.1.50"}
        return (
            mock.patch.object(discovery, "_ping", side_effect=lambda ip: ip in vivos),
            mock.patch.object(discovery, "_tabla_arp", return_value={"10.10.1.50": "aa:bb:cc:dd:ee:ff"}),
            mock.patch.object(discovery, "_nombre_dns", side_effect=lambda ip: "pc-recepcion" if ip == "10.10.1.50" else ""),
        )

    def test_barrido_concilia_inventario_y_guarda_informe(self):
        self.client.force_authenticate(self.ti)
        p1, p2, p3 = self._sondas_falsas()
        with p1, p2, p3:
            resp = self.client.post(reverse("asset-descubrir"), {"fuente": "red_local", "objetivo": "10.10.1.0/25"})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["found_count"], 2)
        self.assertEqual(resp.data["new_count"], 1)
        self.assertEqual(resp.data["unreachable_count"], 1)
        self.assertEqual(resp.data["target"], "10.10.1.0/25")

        nuevo = Asset.objects.get(organization=self.org, ip_address="10.10.1.50")
        self.assertEqual(nuevo.hostname, "pc-recepcion")
        self.assertEqual(nuevo.mac_address, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(nuevo.discovery_source, DiscoverySource.RED_LOCAL)
        self.assertEqual(nuevo.estado, AssetStatus.EN_LINEA)

        self.conocido.refresh_from_db()
        self.apagado.refresh_from_db()
        self.fuera.refresh_from_db()
        self.assertEqual(self.conocido.estado, AssetStatus.EN_LINEA)
        self.assertEqual(self.apagado.estado, AssetStatus.SIN_SENAL)
        self.assertEqual(self.fuera.estado, AssetStatus.DESCONOCIDO)

        self.assertEqual(DiscoveryRun.objects.filter(organization=self.org).count(), 1)
        self.assertTrue(self.RegistroAuditoria.objects.filter(accion="descubrimiento_ejecutado", actor="ti").exists())

        # El historial es visible por API, también para el auditor.
        self.client.force_authenticate(self.auditor)
        lista = self.client.get(reverse("descubrimiento-list"))
        self.assertEqual(lista.status_code, 200)
        self.assertEqual(len(lista.data["results"]), 1)
        self.assertEqual(len(lista.data["results"][0]["hosts"]), 2)

    def test_solo_admin_y_ti_descubren(self):
        self.client.force_authenticate(self.analista)
        self.assertEqual(self.client.post(reverse("asset-descubrir"), {"fuente": "red_local", "objetivo": "10.10.1.0/24"}).status_code, 403)
        self.client.force_authenticate(self.auditor)
        self.assertEqual(self.client.post(reverse("asset-descubrir"), {"fuente": "red_local", "objetivo": "10.10.1.0/24"}).status_code, 403)

    def test_rango_invalido_o_demasiado_grande_devuelve_400(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(reverse("asset-descubrir"), {"fuente": "red_local", "objetivo": "no-es-una-red"}).status_code, 400)
        self.assertEqual(self.client.post(reverse("asset-descubrir"), {"fuente": "red_local", "objetivo": "10.0.0.0/16"}).status_code, 400)
        self.assertEqual(self.client.post(reverse("asset-descubrir"), {"fuente": "red_local"}).status_code, 400)
        self.assertEqual(DiscoveryRun.objects.count(), 0)

    def test_wazuh_sin_configurar_deja_informe_con_error(self):
        self.client.force_authenticate(self.admin)
        with mock.patch.object(discovery.wazuh, "WAZUH_API_URL", ""), mock.patch.object(discovery.wazuh, "fetch_agents", return_value=[]):
            resp = self.client.post(reverse("asset-descubrir"), {"fuente": "wazuh"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], "error")
        self.assertIn("WAZUH_API_URL", resp.data["error"])

    def test_informe_resume_el_inventario_y_exporta_csv(self):
        self.client.force_authenticate(self.analista)
        resp = self.client.get(reverse("asset-informe"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["total"], 3)
        self.assertEqual({e["clave"]: e["total"] for e in resp.data["por_estado"]}["desconocido"], 3)
        self.assertEqual({e["clave"]: e["total"] for e in resp.data["por_tipo"]}["server"], 2)
        self.assertIsNone(resp.data["ultimo_descubrimiento"])

        resp = self.client.get(reverse("asset-informe"), {"formato": "csv"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        contenido = resp.content.decode("utf-8-sig")
        self.assertIn("srv-ehr-01", contenido)
        self.assertEqual(len(contenido.strip().splitlines()), 4)
