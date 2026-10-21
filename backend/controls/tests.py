from django.test import TestCase

from accounts.models import Organization
from assets.models import Asset, AssetType, Criticality
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource, VulnerabilityStatus

from .models import Control
from .serializers import ControlSerializer


class ComplianceScoreTests(TestCase):
    """
    El cumplimiento mostrado en el Panel general y en Controles sale
    de esta fórmula (baseline - 3 por abierta + 3 por cerrada, acotado
    a [20, 99]); estos tests fijan ese comportamiento para notar si
    alguien lo cambia sin querer.
    """

    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.asset = Asset.objects.create(
            organization=self.org, hostname="srv-1", asset_type=AssetType.SERVER, criticality=Criticality.HIGH
        )
        self.source = VulnerabilitySource.objects.create(
            organization=self.org, source_type=SourceType.OPENVAS, name="GVM"
        )
        self.control = Control.objects.create(organization=self.org, name="Control de prueba", baseline_score=80)

    def _crear_vuln(self, status, external_id):
        return Vulnerability.objects.create(
            organization=self.org,
            asset=self.asset,
            source=self.source,
            external_id=external_id,
            title="Hallazgo",
            severity=Severity.MEDIUM,
            status=status,
        )

    def test_sin_hallazgos_el_cumplimiento_es_el_baseline(self):
        data = ControlSerializer(self.control).data
        self.assertEqual(data["compliance_score"], 80)
        self.assertEqual(data["open_findings"], 0)

    def test_cada_hallazgo_abierto_resta_tres_puntos(self):
        for i in range(2):
            v = self._crear_vuln(VulnerabilityStatus.OPEN, f"open-{i}")
            v.controls.add(self.control)

        data = ControlSerializer(self.control).data
        self.assertEqual(data["compliance_score"], 74)  # 80 - 2*3
        self.assertEqual(data["open_findings"], 2)

    def test_el_cumplimiento_no_baja_de_20(self):
        for i in range(30):
            v = self._crear_vuln(VulnerabilityStatus.OPEN, f"open-{i}")
            v.controls.add(self.control)

        data = ControlSerializer(self.control).data
        self.assertEqual(data["compliance_score"], 20)

    def test_cerrar_un_hallazgo_sube_el_cumplimiento_por_encima_del_baseline(self):
        # Por diseño, cerrar un hallazgo no solo "perdona" la penalización de
        # tenerlo abierto: también suma, como señal de progreso de remediación.
        v = self._crear_vuln(VulnerabilityStatus.OPEN, "open-1")
        v.controls.add(self.control)
        self.assertEqual(ControlSerializer(self.control).data["compliance_score"], 77)  # 80 - 3

        v.status = VulnerabilityStatus.CLOSED
        v.save(update_fields=["status"])
        self.assertEqual(ControlSerializer(self.control).data["compliance_score"], 83)  # 80 - 0 + 3


class CatalogoIsoTests(TestCase):
    """HU11: catálogo curado para salud y vínculo automático hallazgo -> control."""

    def setUp(self):
        from accounts.models import Organization
        from assets.models import Asset, AssetType, Criticality
        from vulnerabilities.models import Severity, SourceType, VulnerabilitySource

        self.org = Organization.objects.create(name="Clínica")
        self.asset = Asset.objects.create(
            organization=self.org, hostname="srv", asset_type=AssetType.SERVER, criticality=Criticality.HIGH
        )
        self.source = VulnerabilitySource.objects.create(organization=self.org, source_type=SourceType.OPENVAS, name="GVM")
        self.Severity = Severity

    def test_catalogo_incluye_todos_los_controles_de_la_tabla_de_mapeo(self):
        from controls.catalogo_iso import CONTROLES, MAPEO_CATEGORIA_A_CONTROLES

        codigos = {c[0] for c in CONTROLES}
        for categoria, mapeados in MAPEO_CATEGORIA_A_CONTROLES.items():
            for codigo in mapeados:
                self.assertIn(codigo, codigos, f"{codigo} ({categoria}) falta en el catálogo")

    def test_cargar_catalogo_es_idempotente_y_asigna_tema(self):
        from controls.models import Control
        from controls.services import cargar_catalogo

        cargar_catalogo(self.org)
        n = Control.objects.filter(organization=self.org).count()
        cargar_catalogo(self.org)
        self.assertEqual(Control.objects.filter(organization=self.org).count(), n)
        self.assertEqual(Control.objects.get(organization=self.org, iso_code="8.8").theme, "tecnologico")
        self.assertEqual(Control.objects.get(organization=self.org, iso_code="6.8").theme, "personas")

    def test_hallazgo_con_categoria_se_vincula_solo_a_sus_controles(self):
        from controls.services import cargar_catalogo
        from vulnerabilities.models import Vulnerability

        cargar_catalogo(self.org)
        v = Vulnerability.objects.create(
            organization=self.org, asset=self.asset, source=self.source, external_id="1", title="t",
            severity=self.Severity.HIGH, category="software_desactualizado",
        )
        self.assertEqual(sorted(c.iso_code for c in v.controls.all()), ["8.19", "8.32", "8.8"])
