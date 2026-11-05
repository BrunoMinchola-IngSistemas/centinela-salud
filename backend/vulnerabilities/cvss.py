"""
HU06: puntaje CVSS a partir del vector de métricas base.

Usa la librería `cvss` (Red Hat), que implementa la especificación de
FIRST para CVSS v4.0 y v3.x. Así el puntaje no se tipea: sale de las
métricas, y si las métricas cambian (otro vector), se recalcula al
guardar el hallazgo (ver Vulnerability.save).
"""

from decimal import Decimal

from cvss import CVSS3, CVSS4
from cvss.exceptions import CVSSError


def _clase(vector):
    if vector.startswith("CVSS:4.0/"):
        return CVSS4
    if vector.startswith("CVSS:3."):
        return CVSS3
    return None


def puntaje_desde_vector(vector):
    """Puntaje base (Decimal entre 0.0 y 10.0) o None si el vector no es válido."""
    vector = (vector or "").strip()
    clase = _clase(vector)
    if clase is None:
        return None
    try:
        calculado = clase(vector)
    except (CVSSError, ValueError, KeyError):
        return None
    base = calculado.base_score if clase is CVSS4 else calculado.scores()[0]
    return Decimal(str(base)).quantize(Decimal("0.1"))


def severidad_desde_puntaje(puntaje):
    """Bandas oficiales: 0.1-3.9 baja · 4.0-6.9 media · 7.0-8.9 alta · 9.0-10.0 crítica."""
    p = float(puntaje)
    if p >= 9.0:
        return "critical"
    if p >= 7.0:
        return "high"
    if p >= 4.0:
        return "medium"
    return "low"


def validar_vector(vector):
    """Mensaje de error en español, o None si el vector es válido (o está vacío)."""
    vector = (vector or "").strip()
    if not vector:
        return None
    if _clase(vector) is None:
        return "El vector debe empezar con «CVSS:4.0/» (o «CVSS:3.1/» si el escáner aún reporta v3)."
    if puntaje_desde_vector(vector) is None:
        return "El vector CVSS no es válido: revisa que tenga todas las métricas base obligatorias."
    return None
