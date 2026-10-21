"""Pruebas unitarias de las reglas R1-R5 (vulnerabilities/priority.py)."""

from django.test import SimpleTestCase

from .priority import calcular_prioridad, nivel_desde_cvss


def calc(**kw):
    base = dict(
        cvss=7.5, severidad_declarada="high", exposicion="interna", criticidad="high",
        explotacion_activa=False, datos_clinicos=False,
    )
    base.update(kw)
    return calcular_prioridad(**base)


def reglas(r):
    return [x["regla"] for x in r.reglas]


class BandasCvssTests(SimpleTestCase):
    def test_bandas_cvss_v4(self):
        self.assertEqual(nivel_desde_cvss(0), "none")
        self.assertEqual(nivel_desde_cvss(3.9), "low")
        self.assertEqual(nivel_desde_cvss(4.0), "medium")
        self.assertEqual(nivel_desde_cvss(6.9), "medium")
        self.assertEqual(nivel_desde_cvss(7.0), "high")
        self.assertEqual(nivel_desde_cvss(8.9), "high")
        self.assertEqual(nivel_desde_cvss(9.0), "critical")
        self.assertIsNone(nivel_desde_cvss(None))


class ReglasTests(SimpleTestCase):
    def test_r1_internet_y_criticidad_alta_sube_un_nivel(self):
        r = calc(cvss=7.5, exposicion="internet", criticidad="high")
        self.assertEqual(r.nivel_final, "critical")
        self.assertEqual(reglas(r), ["R1"])

    def test_r1_no_pasa_de_critica(self):
        r = calc(cvss=9.8, exposicion="internet", criticidad="critical")
        self.assertEqual(r.nivel_final, "critical")

    def test_r1_no_aplica_si_criticidad_es_media(self):
        r = calc(cvss=7.5, exposicion="internet", criticidad="medium")
        self.assertEqual(r.nivel_final, "high")
        self.assertEqual(reglas(r), [])

    def test_r2_perimetral_mantiene(self):
        r = calc(cvss=5.0, exposicion="perimetral", criticidad="low")
        self.assertEqual(r.nivel_final, "medium")
        self.assertEqual(reglas(r), ["R2"])

    def test_r3_interna_y_criticidad_baja_baja_un_nivel(self):
        r = calc(cvss=7.5, exposicion="interna", criticidad="medium")
        self.assertEqual(r.nivel_final, "medium")
        self.assertEqual(reglas(r), ["R3"])

    def test_r3_no_baja_de_baja(self):
        r = calc(cvss=2.0, exposicion="interna", criticidad="low")
        self.assertEqual(r.nivel_final, "low")

    def test_r4_explotacion_activa_sube(self):
        r = calc(cvss=5.0, exposicion="interna", criticidad="high", explotacion_activa=True)
        self.assertEqual(r.nivel_final, "high")
        self.assertEqual(reglas(r), ["R4"])

    def test_r5_datos_clinicos_nunca_bajo_alta(self):
        # R3 la bajaría a Baja, pero R5 la sube al piso de Alta.
        r = calc(cvss=5.0, exposicion="interna", criticidad="low", datos_clinicos=True)
        self.assertEqual(r.nivel_final, "high")
        self.assertEqual(reglas(r), ["R3", "R5"])

    def test_r5_no_baja_una_critica(self):
        r = calc(cvss=9.8, datos_clinicos=True)
        self.assertEqual(r.nivel_final, "critical")

    def test_sin_cvss_usa_severidad_declarada(self):
        r = calc(cvss=None, severidad_declarada="medium", exposicion="perimetral")
        self.assertEqual(r.nivel_base, "medium")

    def test_combinacion_r1_r4_r5(self):
        r = calc(cvss=6.0, exposicion="internet", criticidad="critical", explotacion_activa=True, datos_clinicos=True)
        self.assertEqual(r.nivel_final, "critical")
        self.assertEqual(reglas(r), ["R1", "R4", "R5"])
