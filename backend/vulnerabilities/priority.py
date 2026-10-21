"""
Prioridad contextual (HU06/HU07): ajusta la severidad técnica (CVSS v4.0)
según el contexto del activo, con las reglas R1-R5 del documento OE2
(sección "Severidad técnica y prioridad contextual").

Bandas CVSS v4.0: Ninguna 0.0 · Baja 0.1-3.9 · Media 4.0-6.9 ·
Alta 7.0-8.9 · Crítica 9.0-10.0.

Reglas (propuestas en el OE2, "a calibrar en el Sprint 3" — decisión
D5 del documento, pendiente de validar con el asesor/experto):

  R1  Activo expuesto a Internet con criticidad alta o crítica -> sube un nivel (máx. Crítica)
  R2  Activo perimetral                                       -> mantiene el nivel
  R3  Exposición interna con criticidad media o baja          -> baja un nivel (mín. Baja)
  R4  Explotación activa reportada (p. ej. CISA KEV)          -> sube un nivel
  R5  Activo con datos clínicos o personales                  -> nunca menos que Alta (Ley 29733)

Orden de aplicación: primero la regla de exposición (R1/R2/R3, que son
excluyentes entre sí), luego R4, y R5 al final como "piso", para que
ninguna regla anterior pueda bajar un activo con datos clínicos por
debajo de Alta.

Interpretación tomada (para revisar con el asesor): R1 dice "mantiene o
sube un nivel"; aquí se sube un nivel, porque si solo "mantuviera" no
se distinguiría de R2. Si el asesor prefiere otra lectura, se cambia
solo en `_aplicar_exposicion`.

Es un módulo puro (sin base de datos) para poder probar cada regla de
forma aislada y, más adelante, comparar contra la sugerencia del SVM
("línea base solo reglas" que pide el propio documento).
"""

from dataclasses import dataclass, field

NIVELES = ["none", "low", "medium", "high", "critical"]
ETIQUETA = {"none": "Ninguna", "low": "Baja", "medium": "Media", "high": "Alta", "critical": "Crítica"}


def nivel_desde_cvss(cvss):
    if cvss is None:
        return None
    cvss = float(cvss)
    if cvss == 0:
        return "none"
    if cvss < 4.0:
        return "low"
    if cvss < 7.0:
        return "medium"
    if cvss < 9.0:
        return "high"
    return "critical"


def _subir(nivel):
    return NIVELES[min(NIVELES.index(nivel) + 1, len(NIVELES) - 1)]


def _bajar(nivel, minimo="low"):
    return NIVELES[max(NIVELES.index(nivel) - 1, NIVELES.index(minimo))]


@dataclass
class ResultadoPrioridad:
    nivel_base: str
    nivel_final: str
    reglas: list = field(default_factory=list)  # [{"regla": "R1", "efecto": "...", "de": "high", "a": "critical"}]

    def as_dict(self):
        return {
            "nivel_base": self.nivel_base,
            "nivel_final": self.nivel_final,
            "reglas": self.reglas,
        }


def _registrar(resultado, regla, explicacion, antes, despues):
    resultado.reglas.append(
        {
            "regla": regla,
            "explicacion": explicacion,
            "de": antes,
            "a": despues,
        }
    )


def _aplicar_exposicion(nivel, exposicion, criticidad, resultado):
    if exposicion == "internet" and criticidad in ("high", "critical"):
        nuevo = _subir(nivel)
        _registrar(resultado, "R1", "Activo expuesto a Internet con criticidad alta o crítica: sube un nivel.", nivel, nuevo)
        return nuevo
    if exposicion == "perimetral":
        _registrar(resultado, "R2", "Activo perimetral: mantiene el nivel.", nivel, nivel)
        return nivel
    if exposicion == "interna" and criticidad in ("medium", "low"):
        nuevo = _bajar(nivel) if nivel != "none" else nivel
        _registrar(resultado, "R3", "Exposición interna con criticidad media o baja: baja un nivel (mínimo Baja).", nivel, nuevo)
        return nuevo
    return nivel


def calcular_prioridad(*, cvss, severidad_declarada, exposicion, criticidad, explotacion_activa, datos_clinicos):
    """
    Devuelve un ResultadoPrioridad con el nivel final y la lista de
    reglas que se aplicaron (para mostrar "por qué" en la consola: el
    documento pide que cada decisión del agente sea explicable).
    """
    base = nivel_desde_cvss(cvss) or severidad_declarada or "medium"
    resultado = ResultadoPrioridad(nivel_base=base, nivel_final=base)

    nivel = _aplicar_exposicion(base, exposicion, criticidad, resultado)

    if explotacion_activa:
        nuevo = _subir(nivel)
        _registrar(resultado, "R4", "Explotación activa reportada en inteligencia de amenazas: sube un nivel.", nivel, nuevo)
        nivel = nuevo

    if datos_clinicos and NIVELES.index(nivel) < NIVELES.index("high"):
        _registrar(resultado, "R5", "Activo con datos clínicos o personales: no baja de Alta (Ley N.° 29733).", nivel, "high")
        nivel = "high"
    elif datos_clinicos:
        _registrar(resultado, "R5", "Activo con datos clínicos o personales: ya está en Alta o más, se mantiene.", nivel, nivel)

    resultado.nivel_final = nivel
    return resultado


def calcular_para(vulnerability):
    asset = vulnerability.asset
    return calcular_prioridad(
        cvss=vulnerability.cvss_score,
        severidad_declarada=vulnerability.severity,
        exposicion=asset.exposure,
        criticidad=asset.criticality,
        explotacion_activa=vulnerability.actively_exploited,
        datos_clinicos=asset.stores_phi,
    )
