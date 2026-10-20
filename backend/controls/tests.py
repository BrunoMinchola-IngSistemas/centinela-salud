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
