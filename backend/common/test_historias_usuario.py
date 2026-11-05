"""
Validación de las 30 historias de usuario del Product Backlog.

Cada prueba corresponde a un escenario de aceptación ("Dado / Cuando /
Entonces") del documento Product_Backlog.docx. El nombre de la prueba
dice qué HU y qué escenario cubre, para poder citarlo en la tesis:

    python manage.py test common.test_historias_usuario -v 2

Lo que depende de infraestructura (TLS y cifrado en reposo de la
Ley 29733) se valida en el despliegue (deploy/validar_hu.py y la guía
de AWS); aquí se prueba la parte de la aplicación (seudonimización,
acceso a archivos solo por la API, log sin edición).
"""

import io
from datetime import timedelta
from unittest import mock

import requests
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts import mfa
from accounts.models import NivelMadurez, Organization, PeriodicidadReporte, Role
from accounts.models import User as Perfil
from assets import discovery
from assets.models import Asset, AssetType, Criticality, Exposure
from controls.models import Control, EstadoImplementacion
from controls.services import cargar_catalogo
from evidence.models import Evidence
from governance.models import (
    AccionAgente,
    EstadoAccion,
    EstadoSolicitud,
    NivelAutonomia,
    PoliticaAutonomia,
    RegistroAuditoria,
    SolicitudAprobacion,
    TipoAccion,
)
from incidents.models import IncidenteReportado
from informes.models import ReporteGenerado
from integrations.models import FallaIntegracion, RegistroIncompleto
from notificaciones.models import Notificacion, TipoNotificacion
from remediation.models import PlanStatus, RemediationPlan
from vulnerabilities.models import CatalogoCVE, SincronizacionCVE, SourceType, Vulnerability, VulnerabilitySource

PDF_MINIMO = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


class BaseHU(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="SaludMedica (prueba)")

        def crear(username, rol):
            u = User.objects.create_user(username, password="Clave-Segura-2026", email=f"{username}@clinica.pe")
            Perfil.objects.create(user=u, organization=self.org, role=rol)
            return u

        self.admin = crear("gerencia", Role.ADMIN)
        self.ti = crear("ti", Role.IT_OWNER)
        self.cumplimiento = crear("cumplimiento", Role.COMPLIANCE)
        self.personal = crear("personal", Role.STAFF)
        self.analista = crear("analista", Role.ANALYST)
        self.auditor = crear("auditor", Role.AUDITOR)

        self.controles = cargar_catalogo(self.org)
        self.srv = Asset.objects.create(
            organization=self.org, hostname="srv-ehr-01", asset_type=AssetType.SERVER, ip_address="10.10.1.11",
            criticality=Criticality.CRITICAL, stores_phi=True, exposure=Exposure.PERIMETRAL,
        )
        self.pc = Asset.objects.create(
            organization=self.org, hostname="adm-03", asset_type=AssetType.WORKSTATION, ip_address="10.10.1.33",
            criticality=Criticality.MEDIUM,
        )
        self.gvm = VulnerabilitySource.objects.create(organization=self.org, source_type=SourceType.OPENVAS, name="GVM")
        self.wazuh = VulnerabilitySource.objects.create(organization=self.org, source_type=SourceType.WAZUH, name="Wazuh")
        self.ksc = VulnerabilitySource.objects.create(organization=self.org, source_type=SourceType.KASPERSKY, name="KSC")
        self.vuln = Vulnerability.objects.create(
            organization=self.org, asset=self.srv, source=self.gvm, external_id="v-1", cve="CVE-2021-44228",
            title="Log4Shell", severity="critical", cvss_score=10.0, epss_score=0.9, category="software_desactualizado",
        )

    def como(self, user):
        self.client.force_authenticate(user)
        return self.client

    def notifs(self, user, tipo=None):
        qs = Notificacion.objects.filter(destinatario=user)
        return qs.filter(tipo=tipo) if tipo else qs


# ---------------------------------------------------------------- HU01 / HU05

class _Descubrimiento:
    def _sondas(self, vivos):
        return (
            mock.patch.object(discovery, "_ping", side_effect=lambda ip: ip in vivos),
            mock.patch.object(discovery, "_tabla_arp", return_value={}),
            mock.patch.object(discovery, "_nombre_dns", side_effect=lambda ip: "pc-nueva" if ip == "10.10.1.50" else ""),
        )

    def _descubrir(self, user, datos):
        a, b, c = self._sondas({"10.10.1.11", "10.10.1.50"})
        with a, b, c:
            return self.como(user).post(reverse("asset-descubrir"), datos)


class HU01DescubrimientoTests(_Descubrimiento, BaseHU):
    def test_hu01_principal_registra_activos_con_nombre_tipo_ip_y_estado_y_exporta(self):
        self.org.rango_red = "10.10.1.0/26"
        self.org.save()
        resp = self._descubrir(self.ti, {"fuente": "red_local"})  # usa el rango configurado
        self.assertEqual(resp.status_code, 201, resp.data)
        nuevo = Asset.objects.get(organization=self.org, ip_address="10.10.1.50")
        self.assertEqual(nuevo.hostname, "pc-nueva")
        self.assertTrue(nuevo.asset_type)
        self.assertTrue(nuevo.reachable)
        csv = self.como(self.ti).get(reverse("asset-informe"), {"formato": "csv"})
        self.assertEqual(csv.status_code, 200)
        self.assertIn("pc-nueva", csv.content.decode("utf-8-sig"))

    def test_hu01_activo_ya_registrado_se_actualiza_sin_duplicar(self):
        self._descubrir(self.ti, {"fuente": "red_local", "objetivo": "10.10.1.0/26"})
        self._descubrir(self.ti, {"fuente": "red_local", "objetivo": "10.10.1.0/26"})
        self.assertEqual(Asset.objects.filter(organization=self.org, ip_address="10.10.1.11").count(), 1)
        self.assertEqual(Asset.objects.filter(organization=self.org, ip_address="10.10.1.50").count(), 1)
        self.srv.refresh_from_db()
        self.assertIsNotNone(self.srv.last_discovered_at)

    def test_hu01_sin_rango_configurado_muestra_mensaje_y_no_ejecuta(self):
        resp = self._descubrir(self.ti, {"fuente": "red_local"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Debe configurar un rango de red antes de iniciar el descubrimiento", str(resp.data))
        self.assertFalse(Asset.objects.filter(ip_address="10.10.1.50").exists())

    def test_hu01_seguridad_no_permite_barrer_rangos_publicos(self):
        resp = self._descubrir(self.ti, {"fuente": "red_local", "objetivo": "8.8.8.0/28"})
        self.assertEqual(resp.status_code, 400)


class HU05ActivoNuevoTests(_Descubrimiento, BaseHU):
    def test_hu05_principal_activo_nuevo_notifica_a_ti_en_menos_de_15_minutos(self):
        inicio = timezone.now()
        self._descubrir(self.ti, {"fuente": "red_local", "objetivo": "10.10.1.0/26"})
        avisos = self.notifs(self.ti, TipoNotificacion.ACTIVO_NUEVO)
        self.assertEqual(avisos.count(), 1)
        self.assertIn("pc-nueva", avisos.first().titulo)
        self.assertLess(avisos.first().creada_en - inicio, timedelta(minutes=15))

    def test_hu05_activo_ya_conocido_no_genera_nueva_notificacion(self):
        self._descubrir(self.ti, {"fuente": "red_local", "objetivo": "10.10.1.0/26"})
        self._descubrir(self.ti, {"fuente": "red_local", "objetivo": "10.10.1.0/26"})
        self.assertEqual(self.notifs(self.ti, TipoNotificacion.ACTIVO_NUEVO).count(), 1)


# ---------------------------------------------------------------- HU02 / HU04

@override_settings(INTEGRACIONES_DEMO=True)
class HU02RecoleccionTests(BaseHU):
    def setUp(self):
        super().setUp()
        self.p = mock.patch("integrations.sync._configurado", return_value=False)
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_hu02_principal_tres_fuentes_recolectan_sin_intervencion_manual(self):
        from integrations.sync import recolectar_todas

        recolectar_todas()  # lo que corre el programador, sin usuario
        fuentes = set(Vulnerability.objects.filter(organization=self.org).exclude(external_id="v-1").values_list("source__source_type", flat=True))
        self.assertEqual(fuentes, {"openvas", "wazuh", "kaspersky"})
        for s in (self.gvm, self.wazuh, self.ksc):
            s.refresh_from_db()
            self.assertTrue(s.last_sync_ok)

    def test_hu02_fuente_que_no_responde_queda_en_log_de_fallas_y_sigue_con_las_demas(self):
        from integrations import sync

        original = sync._traer

        def traer(source):
            if source.source_type == SourceType.WAZUH:
                raise ConnectionError("Wazuh no responde")
            return original(source)

        with mock.patch.object(sync, "_traer", side_effect=traer):
            sync.sync_all_sources(self.org)
        falla = FallaIntegracion.objects.get(organization=self.org)
        self.assertIn("Wazuh no responde", falla.error)
        self.assertTrue(Vulnerability.objects.filter(source=self.ksc).exists())
        self.assertTrue(Vulnerability.objects.filter(source=self.gvm).exclude(external_id="v-1").exists())

    def test_hu02_proteccion_datos_personales_se_seudonimizan(self):
        from integrations.sync import sync_all_sources

        sync_all_sources(self.org)
        v = Vulnerability.objects.get(source=self.wazuh, external_id="wazuh-demo-sca-101")
        self.assertNotIn("45678912", v.description)
        self.assertNotIn("jperez@saludmedica.pe", v.description)
        self.assertIn("[DNI-", v.description)
        self.assertIn("[CORREO-", v.description)


@override_settings(INTEGRACIONES_DEMO=True)
class HU04NormalizacionTests(BaseHU):
    def test_hu04_principal_formatos_distintos_van_al_mismo_esquema(self):
        from integrations.normalizacion import CAMPOS, faltantes, normalizar
        from integrations.wazuh import NormalizedFinding as Wz

        a = normalizar(Wz(external_id="w1", asset_hostname="pc", asset_ip="", title="SCA", description="", severity="Alta"))
        b = normalizar({"external_id": "g1", "asset_hostname": "", "asset_ip": "10.0.0.1", "title": "X", "cvss_score": 9.1})
        self.assertEqual(set(a), set(CAMPOS))
        self.assertEqual(set(b), set(CAMPOS))
        self.assertEqual(a["severity"], "high")
        self.assertEqual(b["severity"], "critical")  # derivada del CVSS
        self.assertEqual(faltantes(a), [])
        self.assertEqual(faltantes(b), [])

    def test_hu04_registro_incompleto_se_marca_y_excluye_hasta_corregirlo(self):
        from integrations.sync import sync_source

        with mock.patch("integrations.sync._configurado", return_value=False):
            sync_source(self.gvm)
        reg = RegistroIncompleto.objects.get(organization=self.org, external_id="gvm-demo-003")
        self.assertIn("title", reg.campos_faltantes)
        self.assertFalse(Vulnerability.objects.filter(source=self.gvm, external_id="gvm-demo-003").exists())
        resp = self.como(self.ti).post(reverse("registro-incompleto-corregir", args=[reg.id]), {"title": "Prueba sin nombre del escáner"})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(Vulnerability.objects.filter(source=self.gvm, external_id="gvm-demo-003").exists())

    def test_hu04_proteccion_datos_al_normalizar(self):
        from integrations.normalizacion import normalizar

        d = normalizar({"external_id": "x", "title": "t", "severity": "low", "asset_ip": "10.0.0.2",
                        "description": "Paciente HC 123456, teléfono 987 654 321"})
        self.assertNotIn("123456", d["description"])
        self.assertNotIn("987 654 321", d["description"])


# ---------------------------------------------------------------- HU03

class HU03BaseCVETests(BaseHU):
    NVD = [{
        "id": "CVE-2026-0001", "published": "2026-11-04T10:00:00.000", "lastModified": "2026-11-04T11:00:00.000",
        "descriptions": [{"lang": "en", "value": "Nueva vulnerabilidad de prueba"}],
        "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "baseSeverity": "CRITICAL",
                                                     "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}}]},
    }]
    KEV = [{"cveID": "CVE-2021-44228", "dateAdded": "2021-12-10"}]

    def test_hu03_principal_cve_nueva_se_incorpora_en_menos_de_24_horas(self):
        from vulnerabilities import cve_feed

        with mock.patch.object(cve_feed, "_descargar_nvd", return_value=self.NVD), \
             mock.patch.object(cve_feed, "_descargar_kev", return_value=self.KEV):
            sync = cve_feed.sincronizar(horas=24)
        self.assertTrue(sync.ok)
        cve = CatalogoCVE.objects.get(cve_id="CVE-2026-0001")
        self.assertLess(cve.incorporado_en - cve.modificado_en, timedelta(hours=24) + (timezone.now() - cve.modificado_en))
        self.assertEqual(float(cve.cvss_score), 9.8)
        self.vuln.refresh_from_db()
        self.assertTrue(self.vuln.actively_exploited)  # KEV -> R4

    def test_hu03_fuente_no_disponible_conserva_version_y_notifica(self):
        from vulnerabilities import cve_feed

        CatalogoCVE.objects.create(cve_id="CVE-2020-0001", descripcion="previa")
        with mock.patch.object(cve_feed, "_descargar_nvd", side_effect=requests.ConnectionError("NVD caída")):
            sync = cve_feed.sincronizar()
        self.assertFalse(sync.ok)
        self.assertTrue(CatalogoCVE.objects.filter(cve_id="CVE-2020-0001").exists())
        self.assertTrue(self.notifs(self.ti, TipoNotificacion.CVE).filter(titulo__icontains="no se completó").exists())
        resp = self.como(self.ti).get(reverse("cve-sincronizaciones"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["historial"][0]["ok"])


# ---------------------------------------------------------------- HU06 / HU07 / HU25

class HU06CVSSTests(BaseHU):
    def test_hu06_principal_puntaje_cvss_entre_0_y_10_calculado_de_metricas(self):
        resp = self.como(self.analista).post(reverse("vulnerability-list"), {
            "asset": str(self.pc.id), "source": self.gvm.id, "external_id": "m-1", "title": "Prueba",
            "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        v = Vulnerability.objects.get(external_id="m-1")
        self.assertEqual(float(v.cvss_score), 9.8)
        self.assertTrue(0 <= float(v.cvss_score) <= 10)
        self.assertEqual(v.severity, "critical")

    def test_hu06_cambio_de_metricas_recalcula_el_puntaje(self):
        self.vuln.cvss_vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
        self.vuln.save()
        resp = self.como(self.analista).patch(reverse("vulnerability-detail", args=[self.vuln.id]),
                                              {"cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.vuln.refresh_from_db()
        self.assertEqual(float(self.vuln.cvss_score), 3.1)
        self.assertEqual(self.vuln.severity, "low")

    def test_hu06_vector_invalido_se_rechaza(self):
        resp = self.como(self.analista).patch(reverse("vulnerability-detail", args=[self.vuln.id]),
                                              {"cvss_vector": "CVSS:3.1/AV:N"}, format="json")
        self.assertEqual(resp.status_code, 400)


class HU07ImpactoTests(BaseHU):
    def test_hu07_principal_muestra_activos_criticos_relacionados_y_nivel_de_impacto(self):
        Vulnerability.objects.create(organization=self.org, asset=self.pc, source=self.gvm, external_id="v-2",
                                     cve="CVE-2021-44228", title="Log4Shell", severity="critical", cvss_score=10.0)
        resp = self.como(self.analista).get(reverse("vulnerability-detail", args=[self.vuln.id]))
        self.assertIn(resp.data["nivel_impacto"], ["bajo", "medio", "alto", "critico"])
        hosts = {a["hostname"]: a for a in resp.data["activos_relacionados"]}
        self.assertTrue(hosts["srv-ehr-01"]["critico"])
        self.assertIn("adm-03", hosts)

    def test_hu07_sin_activo_queda_pendiente_de_asociacion(self):
        resp = self.como(self.analista).post(reverse("vulnerability-list"), {
            "source": self.gvm.id, "external_id": "sin-activo", "title": "Telnet en IP desconocida", "severity": "high",
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["nivel_impacto"], "pendiente_asociacion")
        self.assertEqual(resp.data["contextual_priority"], "")


class HU25ExplicacionTests(BaseHU):
    def test_hu25_explicacion_de_2_a_3_lineas_cita_cvss_activo_y_control(self):
        resp = self.como(self.cumplimiento).get(reverse("vulnerability-detail", args=[self.vuln.id]))
        lineas = resp.data["explicacion"]
        texto = " ".join(lineas)
        self.assertGreaterEqual(len(lineas), 2)
        self.assertIn("CVSS 10.0", texto)
        self.assertIn("srv-ehr-01", texto)
        self.assertIn("8.8", texto)


# ---------------------------------------------------------------- HU08

class HU08ClasificacionTests(BaseHU):
    def test_hu08_principal_clasificacion_sugerida_con_accuracy_y_f1(self):
        resp = self.como(self.analista).post(reverse("vulnerability-clasificar", args=[self.vuln.id]))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn(resp.data["riesgo_sugerido"], ["low", "medium", "high", "critical"])
        self.assertTrue(0 < resp.data["modelo"]["accuracy"] <= 1)
        self.assertTrue(0 < resp.data["modelo"]["f1_macro"] <= 1)

    def test_hu08_correccion_manual_conserva_ambas_clasificaciones(self):
        self.como(self.ti).post(reverse("vulnerability-clasificar", args=[self.vuln.id]))
        self.vuln.refresh_from_db()
        sugerido = self.vuln.riesgo_sugerido
        corregido = "medium" if sugerido != "medium" else "low"
        resp = self.como(self.ti).post(reverse("vulnerability-corregir-clasificacion", args=[self.vuln.id]),
                                       {"riesgo": corregido, "motivo": "Equipo aislado físicamente."})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.vuln.refresh_from_db()
        self.assertEqual(self.vuln.riesgo_sugerido, sugerido)
        self.assertEqual(self.vuln.riesgo_corregido, corregido)
        self.assertEqual(self.vuln.riesgo_corregido_por, "ti")
        self.assertTrue(RegistroAuditoria.objects.filter(accion="clasificacion_corregida").exists())


# ---------------------------------------------------------------- HU09 / HU10

class HU09MatrizTests(BaseHU):
    def test_hu09_principal_matriz_probabilidad_por_impacto_actualizada(self):
        resp = self.como(self.cumplimiento).get(reverse("vulnerability-matriz-riesgos"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["celdas"]), 25)
        self.assertEqual(resp.data["total"], 1)
        Vulnerability.objects.create(organization=self.org, asset=self.pc, source=self.gvm, external_id="v-3", title="Otra", severity="low")
        self.assertEqual(self.como(self.cumplimiento).get(reverse("vulnerability-matriz-riesgos")).data["total"], 2)

    def test_hu09_filtro_por_nivel_o_activo(self):
        Vulnerability.objects.create(organization=self.org, asset=self.pc, source=self.gvm, external_id="v-3", title="Otra", severity="low")
        por_activo = self.como(self.cumplimiento).get(reverse("vulnerability-matriz-riesgos"), {"asset": str(self.pc.id)})
        self.assertEqual(por_activo.data["total"], 1)
        nivel = next(c["nivel"] for c in por_activo.data["celdas"] if c["total"])
        por_nivel = self.como(self.cumplimiento).get(reverse("vulnerability-matriz-riesgos"), {"nivel": nivel})
        self.assertTrue(all(c["nivel"] == nivel for c in por_nivel.data["celdas"] if c["total"]))


class HU10HistorialTests(BaseHU):
    def test_hu10_principal_filtra_por_fecha_severidad_y_activo_y_grafica_3_meses(self):
        for i, dias in enumerate([100, 70, 40, 10]):
            v = Vulnerability.objects.create(organization=self.org, asset=self.pc, source=self.gvm, external_id=f"h{i}",
                                             title=f"H{i}", severity="medium")
            Vulnerability.objects.filter(pk=v.pk).update(first_detected_at=timezone.now() - timedelta(days=dias))
        c = self.como(self.cumplimiento)
        desde = (timezone.localdate() - timedelta(days=50)).isoformat()
        filtrado = c.get(reverse("vulnerability-list"), {"detectado_desde": desde, "severity": "medium", "asset": str(self.pc.id)})
        self.assertEqual(filtrado.data["count"], 2)
        t = c.get(reverse("vulnerability-tendencia"), {"meses": 3})
        self.assertTrue(t.data["suficiente"])
        self.assertEqual(len(t.data["meses"]), 3)

    def test_hu10_menos_de_un_mes_de_operacion_muestra_mensaje(self):
        t = self.como(self.cumplimiento).get(reverse("vulnerability-tendencia"))
        self.assertFalse(t.data["suficiente"])
        self.assertIn("no hay suficiente historial", t.data["mensaje"])


# ---------------------------------------------------------------- HU11 - HU16

class HU11ControlesTests(BaseHU):
    def test_hu11_principal_hallazgo_se_vincula_a_controles_del_anexo_a(self):
        self.assertEqual(sorted(c.iso_code for c in self.vuln.controls.all()), ["8.19", "8.32", "8.8"])

    def test_hu11_control_sin_evidencia_queda_como_brecha_pendiente(self):
        url = reverse("control-detail", args=[self.controles["8.8"].id])
        self.assertTrue(self.como(self.cumplimiento).get(url).data["brecha_pendiente"])
        archivo = SimpleUploadedFile("acta.pdf", PDF_MINIMO, content_type="application/pdf")
        self.como(self.cumplimiento).post(reverse("evidence-list"), {"name": "Acta", "control": self.controles["8.8"].id, "archivo": archivo})
        self.assertFalse(self.como(self.cumplimiento).get(url).data["brecha_pendiente"])


class HU12MadurezTests(BaseHU):
    def test_hu12_principal_matriz_agrupada_por_4_dominios_segun_madurez(self):
        self.org.nivel_madurez = NivelMadurez.GESTIONADO
        self.org.save()
        resp = self.como(self.cumplimiento).get(reverse("control-matriz-aplicables"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([d["dominio"] for d in resp.data["dominios"]], ["organizacional", "personas", "fisico", "tecnologico"])
        filas = [f for d in resp.data["dominios"] for f in d["controles"]]
        self.assertTrue(all(f["aplicabilidad"] == "aplicable" for f in filas if f["madurez_minima"] <= 2))
        self.assertTrue(any(f["aplicabilidad"] != "aplicable" for f in filas))

    def test_hu12_madurez_no_configurada_pide_completarla(self):
        resp = self.como(self.cumplimiento).get(reverse("control-matriz-aplicables"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("nivel de madurez", str(resp.data))


class HU13CumplimientoTests(BaseHU):
    def test_hu13_principal_porcentaje_por_dominio(self):
        resp = self.como(self.cumplimiento).get(reverse("control-por-tema"))
        self.assertEqual(len(resp.data["dominios"]), 4)
        self.assertTrue(all(0 <= d["cumplimiento"] <= 100 for d in resp.data["dominios"]))

    def test_hu13_cambio_de_estado_recalcula_el_porcentaje(self):
        c = self.como(self.cumplimiento)
        antes = {d["dominio"]: d["cumplimiento"] for d in c.get(reverse("control-por-tema")).data["dominios"]}
        r = c.patch(reverse("control-detail", args=[self.controles["6.3"].id]), {"estado_implementacion": "implementado"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        despues = {d["dominio"]: d["cumplimiento"] for d in c.get(reverse("control-por-tema")).data["dominios"]}
        self.assertGreater(despues["personas"], antes["personas"])
        self.assertTrue(RegistroAuditoria.objects.filter(accion="control_estado_cambiado", actor="cumplimiento").exists())


class HU14EvidenciaTests(BaseHU):
    def test_hu14_principal_archivo_asociado_al_control_con_fecha_y_responsable(self):
        archivo = SimpleUploadedFile("politica respaldo.pdf", PDF_MINIMO, content_type="application/pdf")
        resp = self.como(self.cumplimiento).post(reverse("evidence-list"), {
            "name": "Política de respaldo", "control": self.controles["8.13"].id, "archivo": archivo,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        e = Evidence.objects.get(id=resp.data["id"])
        self.assertEqual(e.control, self.controles["8.13"])
        self.assertEqual(e.created_by, "cumplimiento")
        self.assertIsNotNone(e.created_at)
        self.assertEqual(len(e.sha256_hash), 64)
        descarga = self.como(self.auditor).get(reverse("evidence-descargar", args=[e.id]))
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(b"".join(descarga.streaming_content), PDF_MINIMO)
        self.assertEqual(descarga["X-Integridad-SHA256"], "ok")

    def test_hu14_archivo_no_valido_se_rechaza_con_mensaje(self):
        for nombre, contenido in [("virus.exe", b"MZ\x90\x00"), ("falso.pdf", b"MZ\x90\x00nopdf")]:
            archivo = SimpleUploadedFile(nombre, contenido)
            resp = self.como(self.cumplimiento).post(reverse("evidence-list"), {"name": "x", "control": self.controles["8.13"].id, "archivo": archivo})
            self.assertEqual(resp.status_code, 400)
            self.assertIn("Formato de archivo no válido", str(resp.data))

    def test_hu14_proteccion_nombre_sin_datos_personales_y_descarga_auditada(self):
        archivo = SimpleUploadedFile("informe 45678912.pdf", PDF_MINIMO)
        resp = self.como(self.cumplimiento).post(reverse("evidence-list"), {"name": "x", "control": self.controles["8.13"].id, "archivo": archivo})
        e = Evidence.objects.get(id=resp.data["id"])
        self.assertNotIn("45678912", e.nombre_original)
        self.assertNotIn("45678912", e.archivo.name)
        self.como(self.ti).get(reverse("evidence-descargar", args=[e.id]))
        self.assertTrue(RegistroAuditoria.objects.filter(accion="evidencia_descargada", actor="ti").exists())


class HU15RecomendacionesTests(BaseHU):
    def test_hu15_principal_ordenadas_por_criticidad_y_costo_y_exportables(self):
        resp = self.como(self.cumplimiento).get(reverse("control-recomendaciones"))
        filas = resp.data["recomendaciones"]
        orden = {"alto": 0, "medio": 1, "bajo": 2}
        claves = [(orden[f["criticidad"]], 2 - orden[f["costo"]]) for f in filas]
        self.assertEqual(claves, sorted(claves))
        for formato, firma in (("xlsx", b"PK"), ("pdf", b"%PDF")):
            archivo = self.como(self.cumplimiento).get(reverse("control-recomendaciones"), {"formato": formato})
            self.assertEqual(archivo.status_code, 200)
            self.assertTrue(archivo.content.startswith(firma))

    def test_hu15_sin_controles_pendientes_lo_indica(self):
        Control.objects.filter(organization=self.org).update(estado_implementacion=EstadoImplementacion.IMPLEMENTADO)
        resp = self.como(self.cumplimiento).get(reverse("control-recomendaciones"))
        self.assertEqual(resp.data["recomendaciones"], [])
        self.assertEqual(resp.data["mensaje"], "No existen controles pendientes por recomendar.")


class HU16PanelGerenciaTests(BaseHU):
    def test_hu16_principal_porcentaje_global_iso_y_ley_29733(self):
        resp = self.como(self.admin).get(reverse("ejecutivo-resumen"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("cumplimiento_global", resp.data)
        self.assertIn("cumplimiento_ley_29733", resp.data)

    def test_hu16_cambio_de_estado_se_refleja_sin_recargar_manual(self):
        antes = self.como(self.admin).get(reverse("ejecutivo-resumen")).data["cumplimiento_ley_29733"]
        self.como(self.cumplimiento).patch(reverse("control-detail", args=[self.controles["5.34"].id]),
                                           {"estado_implementacion": "implementado"}, format="json")
        despues = self.como(self.admin).get(reverse("ejecutivo-resumen")).data["cumplimiento_ley_29733"]
        self.assertGreater(despues, antes)


# ---------------------------------------------------------------- HU17 - HU19

class HU17PlanTests(BaseHU):
    def test_hu17_principal_genera_acciones_con_responsable_plazo_y_estado_exportables(self):
        resp = self.como(self.cumplimiento).post(reverse("remediation-plan-generar"), {})
        self.assertEqual(resp.status_code, 201, resp.data)
        plan = RemediationPlan.objects.get(vulnerability=self.vuln)
        self.assertEqual(plan.owner_name, "ti")
        self.assertEqual(plan.status, PlanStatus.PENDING)
        self.assertEqual(plan.due_date, timezone.localdate() + timedelta(days=7))
        for formato, firma in (("pdf", b"%PDF"), ("xlsx", b"PK")):
            r = self.como(self.cumplimiento).get(reverse("remediation-plan-exportar"), {"formato": formato})
            self.assertTrue(r.content.startswith(firma))

    def test_hu17_sin_responsable_disponible_queda_pendiente_de_asignacion(self):
        self.ti.is_active = False
        self.ti.save()
        resp = self.como(self.cumplimiento).post(reverse("remediation-plan-generar"), {})
        self.assertTrue(resp.data["planes"][0]["responsable_pendiente"])
        r = self.como(self.cumplimiento).get(reverse("remediation-plan-exportar"), {"formato": "csv"})
        self.assertIn("Responsable pendiente de asignación", r.content.decode("utf-8-sig"))


class HU18AutonomiaTests(BaseHU):
    def setUp(self):
        super().setUp()
        self.plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate())

    def test_hu18_principal_accion_de_lista_blanca_se_ejecuta_y_queda_en_log(self):
        resp = self.como(self.ti).post(reverse("accion-agente-list"), {"plan": self.plan.id, "tipo_accion": "notificar"})
        self.assertEqual(resp.data["estado"], EstadoAccion.EJECUTADA)
        log = RegistroAuditoria.objects.get(accion="accion_ejecutada")
        self.assertEqual(log.modalidad, NivelAutonomia.AUTONOMO)
        self.assertTrue(log.detalle["autonoma"])

    def test_hu18_capacidad_autonoma_desactivada_queda_pendiente_manual(self):
        r = self.como(self.ti).patch(reverse("organizacion"), {"ejecucion_autonoma_activa": False}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        resp = self.como(self.ti).post(reverse("accion-agente-list"), {"plan": self.plan.id, "tipo_accion": "abrir_ticket"})
        self.assertEqual(resp.data["estado"], EstadoAccion.PENDIENTE_MANUAL)
        self.assertFalse(RegistroAuditoria.objects.filter(accion="accion_ejecutada").exists())


class HU19EstadoTests(BaseHU):
    def test_hu19_cambio_de_estado_queda_con_fecha_y_usuario_y_se_ve_en_el_panel(self):
        plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate())
        r = self.como(self.ti).patch(reverse("remediation-plan-advance", args=[plan.id]))
        self.assertEqual(r.data["status"], PlanStatus.IN_PROGRESS)
        log = RegistroAuditoria.objects.get(accion="plan_avanzado")
        self.assertEqual(log.actor, "ti")
        self.assertIsNotNone(log.creado_en)
        self.como(self.ti).patch(reverse("remediation-plan-advance", args=[plan.id]))
        panel = self.como(self.ti).get(reverse("dashboard-summary")).data
        self.assertEqual(panel["open_count"], 1)
        self.vuln.refresh_from_db()
        self.assertEqual(self.vuln.status, "in_verification")


# ---------------------------------------------------------------- HU20 - HU22

class HU20RiskScoreTests(BaseHU):
    def test_hu20_risk_score_con_semaforo_en_lenguaje_no_tecnico(self):
        r = self.como(self.admin).get(reverse("ejecutivo-resumen")).data["riesgo"]
        self.assertTrue(0 <= r["score"] <= 100)
        self.assertIn(r["semaforo"], ["verde", "ambar", "rojo"])
        self.assertIn("problema", r["mensaje"])
        self.assertNotIn("CVSS", r["mensaje"])


class HU21ReportesTests(BaseHU):
    def test_hu21_principal_reporte_periodico_pdf_y_excel_con_resumen_ejecutivo(self):
        from informes.reportes import generar_reportes_periodicos

        self.org.periodicidad_reporte = PeriodicidadReporte.SEMANAL
        self.org.save()
        generados = generar_reportes_periodicos()
        self.assertEqual({r.formato for r in generados}, {"pdf", "xlsx"})
        pdf = ReporteGenerado.objects.get(formato="pdf")
        self.assertTrue(pdf.automatico)
        self.assertTrue(pdf.archivo.open("rb").read(4) == b"%PDF")
        self.assertEqual(generar_reportes_periodicos(), [])  # no repite antes del periodo
        d = self.como(self.cumplimiento).get(reverse("reporte-descargar", args=[pdf.id]))
        self.assertEqual(d.status_code, 200)

    def test_hu21_sin_periodicidad_pide_configurarla(self):
        r = self.como(self.cumplimiento).post(reverse("reporte-generar"), {"formato": "pdf"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Debe configurar la periodicidad", str(r.data))


class HU22VencimientoTests(BaseHU):
    def test_hu22_critica_vencida_notifica_y_se_marca_vencida(self):
        from vulnerabilities.vencimientos import revisar_vencimientos

        RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate() - timedelta(days=1))
        avisadas = revisar_vencimientos()
        self.assertEqual(len(avisadas), 1)
        self.assertTrue(self.notifs(self.ti, TipoNotificacion.VENCIMIENTO).exists())
        self.assertTrue(self.notifs(self.admin, TipoNotificacion.VENCIMIENTO).exists())
        detalle = self.como(self.ti).get(reverse("vulnerability-detail", args=[self.vuln.id])).data
        self.assertTrue(detalle["is_overdue"])
        self.assertEqual(revisar_vencimientos(), [])  # se avisa una sola vez


# ---------------------------------------------------------------- HU23 / HU24

class HU23PoliticaTests(BaseHU):
    def test_hu23_cambio_registrado_y_alto_impacto_bloqueado_hasta_aprobacion(self):
        pol = PoliticaAutonomia.objects.create(organization=self.org, tipo_accion=TipoAccion.APLICAR_PARCHE, nivel=NivelAutonomia.ASISTIDO)
        r = self.como(self.admin).patch(reverse("politica-autonomia-detail", args=[pol.id]), {"nivel": "con_aprobacion"}, format="json")
        self.assertEqual(r.status_code, 200)
        log = RegistroAuditoria.objects.get(accion="politica_autonomia_cambiada")
        self.assertEqual(log.actor, "gerencia")
        plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate())
        accion = self.como(self.ti).post(reverse("accion-agente-list"), {"plan": plan.id, "tipo_accion": "aislar_servidor"}).data
        self.assertEqual(accion["estado"], EstadoAccion.PENDIENTE_APROBACION)
        self.assertEqual(self.como(self.ti).post(reverse("accion-agente-ejecutar", args=[accion["id"]])).status_code, 400)
        self.como(self.admin).post(reverse("solicitud-aprobacion-aprobar", args=[accion["solicitud"]]), {"comentario": "ok"})
        self.assertEqual(AccionAgente.objects.get(id=accion["id"]).estado, EstadoAccion.EJECUTADA)

    def test_hu23_solo_la_lista_blanca_puede_ser_autonoma(self):
        pol = PoliticaAutonomia.objects.create(organization=self.org, tipo_accion=TipoAccion.AISLAR_SERVIDOR, nivel=NivelAutonomia.CON_APROBACION)
        r = self.como(self.admin).patch(reverse("politica-autonomia-detail", args=[pol.id]), {"nivel": "autonomo"}, format="json")
        self.assertEqual(r.status_code, 400)


class HU24AprobacionTests(BaseHU):
    def setUp(self):
        super().setUp()
        self.plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate())

    def test_hu24_principal_solicitud_con_riesgo_y_efecto_a_gerencia_sin_ejecutar(self):
        accion = self.como(self.ti).post(reverse("accion-agente-list"), {"plan": self.plan.id, "tipo_accion": "aislar_servidor"}).data
        s = SolicitudAprobacion.objects.get(id=accion["solicitud"])
        self.assertTrue(s.riesgo_de_no_actuar and s.efecto_esperado)
        self.assertEqual(s.plan.vulnerability, self.vuln)
        aviso = self.notifs(self.admin, TipoNotificacion.APROBACION).get()
        self.assertIn("Log4Shell", aviso.mensaje)
        self.assertEqual(AccionAgente.objects.get(id=accion["id"]).estado, EstadoAccion.PENDIENTE_APROBACION)

    def test_hu24_sin_respuesta_en_plazo_escala_al_segundo_responsable(self):
        from governance.agente import escalar_vencidas

        self.org.responsable_escalamiento = self.ti
        self.org.save()
        s = SolicitudAprobacion.objects.create(plan=self.plan, tipo_accion="aislar_servidor", riesgo_de_no_actuar="r",
                                               efecto_esperado="e", plazo=timezone.now() - timedelta(minutes=1))
        escalar_vencidas()
        s.refresh_from_db()
        self.assertEqual(s.estado, EstadoSolicitud.ESCALADA)
        self.assertEqual(s.escalado_a, "ti")
        self.assertTrue(self.notifs(self.ti, TipoNotificacion.ESCALAMIENTO).exists())
        r = self.como(self.ti).post(reverse("solicitud-aprobacion-aprobar", args=[s.id]), {"comentario": "Escalado: apruebo"})
        self.assertEqual(r.status_code, 200)


# ---------------------------------------------------------------- HU26 / HU27

class HU26AsistenteTests(BaseHU):
    def test_hu26_principal_responde_con_los_datos_recolectados(self):
        r = self.como(self.ti).post(reverse("asistente-preguntar"), {"pregunta": "¿Cuántas vulnerabilidades críticas tenemos?"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["datos_suficientes"])
        self.assertIn("Log4Shell", r.data["respuesta"])

    def test_hu26_sin_informacion_suficiente_lo_dice_explicitamente(self):
        r = self.como(self.ti).post(reverse("asistente-preguntar"), {"pregunta": "¿Cuántos pacientes atendimos ayer?"})
        self.assertFalse(r.data["datos_suficientes"])
        self.assertIn("No tengo datos suficientes", r.data["respuesta"])


class HU27AuditoriaTests(BaseHU):
    def test_hu27_principal_decision_registrada_con_fecha_hallazgo_decision_y_modalidad(self):
        plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate())
        self.como(self.ti).post(reverse("accion-agente-list"), {"plan": plan.id, "tipo_accion": "notificar"})
        log = RegistroAuditoria.objects.get(accion="accion_ejecutada")
        self.assertIsNotNone(log.creado_en)
        self.assertEqual(log.detalle["hallazgo"], "Log4Shell")
        self.assertEqual(log.detalle["tipo_accion"], "notificar")
        self.assertIn(log.modalidad, NivelAutonomia.values)

    def test_hu27_intento_de_modificar_el_log_se_deniega(self):
        log = RegistroAuditoria.objects.create(organization=self.org, actor="x", accion="y", modalidad="autonomo", objeto_tipo="t", objeto_id="1")
        url = reverse("registro-auditoria-detail", args=[log.id])
        self.assertEqual(self.como(self.admin).patch(url, {"accion": "z"}, format="json").status_code, 405)
        self.assertEqual(self.como(self.admin).delete(url).status_code, 405)
        log.accion = "otra"
        with self.assertRaises(ValueError):
            log.save()


# ---------------------------------------------------------------- HU28 / HU29

class HU28RolesTests(BaseHU):
    def test_hu28_principal_cada_rol_accede_a_sus_modulos(self):
        casos = [
            (self.admin, "ejecutivo-resumen"), (self.ti, "asset-list"), (self.cumplimiento, "control-list"),
            (self.personal, "incidente-list"), (self.analista, "vulnerability-list"), (self.auditor, "registro-auditoria-list"),
        ]
        for user, ruta in casos:
            self.assertEqual(self.como(user).get(reverse(ruta)).status_code, 200, f"{user.username} -> {ruta}")
        me = self.como(self.personal).get(reverse("auth-me")).data
        self.assertEqual(sorted(me["modulos"]), ["configuracion", "incidentes", "notificaciones"])

    def test_hu28_acceso_fuera_de_rol_se_deniega_con_mensaje(self):
        for user, ruta in [(self.personal, "vulnerability-list"), (self.personal, "dashboard-summary"),
                           (self.ti, "ejecutivo-resumen"), (self.cumplimiento, "asset-list")]:
            r = self.como(user).get(reverse(ruta))
            self.assertEqual(r.status_code, 403, f"{user.username} -> {ruta}")
            self.assertIn("Permisos insuficientes", str(r.data))


class HU29AccesoSeguroTests(BaseHU):
    def _login(self, clave="Clave-Segura-2026", usuario="ti"):
        self.client.force_authenticate(None)
        return self.client.post(reverse("api-login"), {"username": usuario, "password": clave})

    def test_hu29_principal_credenciales_y_segundo_factor_conceden_acceso(self):
        self.client.force_authenticate(self.ti)
        datos = self.client.post(reverse("auth-mfa-paso", args=["iniciar"])).data
        self.assertTrue(datos["qr"].startswith("data:image/svg+xml"))
        r = self.client.post(reverse("auth-mfa-paso", args=["activar"]), {"codigo": mfa.codigo_actual(datos["secreto"])})
        self.assertTrue(r.data["activo"])

        paso1 = self._login()
        self.assertTrue(paso1.data["mfa_requerido"])
        self.assertNotIn("token", paso1.data)
        malo = self.client.post(reverse("api-login-mfa"), {"mfa_token": paso1.data["mfa_token"], "codigo": "000000"})
        self.assertEqual(malo.status_code, 400)
        paso2 = self.client.post(reverse("api-login-mfa"), {"mfa_token": paso1.data["mfa_token"], "codigo": mfa.codigo_actual(datos["secreto"])})
        self.assertEqual(paso2.status_code, 200, paso2.data)
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {paso2.data['token']}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 200)

    def test_hu29_cinco_intentos_fallidos_bloquean_la_cuenta(self):
        for _ in range(4):
            self.assertEqual(self._login("mala").status_code, 400)
        quinto = self._login("mala")
        self.assertEqual(quinto.status_code, 423)
        self.assertEqual(self._login().status_code, 423)  # ni con la clave correcta
        self.assertTrue(RegistroAuditoria.objects.filter(accion="cuenta_bloqueada").exists())
        self.assertTrue(self.notifs(self.admin, TipoNotificacion.SEGURIDAD).exists())

    def test_hu29_totp_cumple_vectores_del_rfc_6238(self):
        import hashlib

        clave = b"12345678901234567890"
        self.assertEqual(mfa.hotp(clave, 59 // 30, digitos=8, algoritmo=hashlib.sha1), "94287082")
        self.assertEqual(mfa.hotp(clave, 1111111109 // 30, digitos=8, algoritmo=hashlib.sha1), "07081804")

    @override_settings(TOKEN_TTL_HORAS=1)
    def test_hu29_token_expira(self):
        from rest_framework.authtoken.models import Token

        token = self._login().data["token"]
        Token.objects.filter(key=token).update(created=timezone.now() - timedelta(hours=2))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(self.client.get(reverse("auth-me")).status_code, 401)


# ---------------------------------------------------------------- HU30

class HU30IncidenteTests(BaseHU):
    def test_hu30_principal_reporte_en_3_campos_evaluado_y_ti_avisado_al_momento(self):
        r = self.como(self.personal).post(reverse("incidente-list"), {
            "descripcion": "Me llegó un correo del banco pidiendo mi contraseña y di click al enlace",
            "lugar": "Admisión", "ocurrido_en": timezone.now().isoformat(),
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["evaluacion_categoria"], "phishing")
        self.assertEqual(r.data["evaluacion_severidad"], "high")
        aviso = self.notifs(self.ti, TipoNotificacion.INCIDENTE).get()
        self.assertIn("phishing", aviso.titulo.lower())

    def test_hu30_reporte_incompleto_no_se_procesa(self):
        r = self.como(self.personal).post(reverse("incidente-list"), {"descripcion": "algo raro", "lugar": ""})
        self.assertEqual(r.status_code, 400)
        self.assertIn("lugar", r.data)
        self.assertIn("ocurrido_en", r.data)
        self.assertFalse(IncidenteReportado.objects.exists())

    def test_hu30_proteccion_datos_personales_seudonimizados(self):
        self.como(self.personal).post(reverse("incidente-list"), {
            "descripcion": "El paciente con DNI 45678912 dejó su historia clínica 556677 en recepción",
            "lugar": "Recepción", "ocurrido_en": timezone.now().isoformat(),
        })
        inc = IncidenteReportado.objects.get()
        self.assertNotIn("45678912", inc.descripcion)
        self.assertNotIn("556677", inc.descripcion)
        self.assertEqual(inc.evaluacion_categoria, "fuga_datos")


# ---------------------------------------------------------------- Seguridad (revisión previa al despliegue)

class SeguridadDespliegueTests(BaseHU):
    def test_personal_solo_ve_su_propia_cuenta_en_el_directorio(self):
        r = self.como(self.personal).get(reverse("miembro-list"))
        self.assertEqual([m["username"] for m in r.data], ["personal"])

    def test_exportaciones_neutralizan_formulas(self):
        from informes.exportar import csv_bytes

        contenido = csv_bytes(["t"], [["=HYPERLINK(\"http://x\")"], ["-"]]).decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", contenido)
        self.assertNotIn("'-", contenido)  # el "-" de "sin dato" no se altera

    def test_api_sin_sesion_responde_401_y_salud_es_publica(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("vulnerability-list")).status_code, 401)
        self.assertEqual(self.client.get(reverse("salud")).status_code, 200)

    def test_un_auditor_no_puede_subir_evidencias_ni_generar_planes(self):
        archivo = SimpleUploadedFile("a.pdf", PDF_MINIMO)
        self.assertEqual(self.como(self.auditor).post(reverse("evidence-list"), {"name": "x", "control": self.controles["8.8"].id, "archivo": archivo}).status_code, 403)
        self.assertEqual(self.como(self.auditor).post(reverse("remediation-plan-generar"), {}).status_code, 403)

    def test_aislamiento_entre_clinicas_en_endpoints_nuevos(self):
        otra = Organization.objects.create(name="Otra clínica")
        u = User.objects.create_user("intruso", password="Clave-Segura-2026")
        Perfil.objects.create(user=u, organization=otra, role=Role.ADMIN)
        c = self.como(u)
        self.assertEqual(c.get(reverse("vulnerability-matriz-riesgos")).data["total"], 0)
        self.assertEqual(c.get(reverse("evidence-list")).data["count"], 0)
        self.assertEqual(c.get(reverse("vulnerability-detail", args=[self.vuln.id])).status_code, 404)
        plan = RemediationPlan.objects.create(vulnerability=self.vuln, owner_name="ti", due_date=timezone.localdate())
        self.assertEqual(c.post(reverse("accion-agente-list"), {"plan": plan.id, "tipo_accion": "notificar"}).status_code, 400)
        self.assertEqual(c.get(reverse("notificacion-list")).data["count"], 0)
