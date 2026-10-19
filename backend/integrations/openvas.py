"""
Cliente hacia OpenVAS/GVM mediante el protocolo GMP (Greenbone
Management Protocol), típicamente sobre TLS en el puerto 9390.

Se usa python-gvm (https://github.com/greenbone/python-gvm) en la
implementación real; aquí se deja la interfaz que el resto del
backend necesita, para no acoplar todo el proyecto a esa librería
hasta que se instale en el entorno de despliegue final.
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OPENVAS_GMP_HOST = os.getenv("OPENVAS_GMP_HOST", "")
OPENVAS_GMP_PORT = int(os.getenv("OPENVAS_GMP_PORT", "9390"))
OPENVAS_USERNAME = os.getenv("OPENVAS_USERNAME", "")
OPENVAS_PASSWORD = os.getenv("OPENVAS_PASSWORD", "")

SEVERITY_BANDS = [
    (9.0, "critical"),
    (7.0, "high"),
    (4.0, "medium"),
    (0.0, "low"),
]


@dataclass
class NormalizedFinding:
    external_id: str
    asset_hostname: str
    asset_ip: str
    title: str
    description: str
    severity: str
    cve: str = ""
    cvss_score: float | None = None


def _severity_band(cvss: float) -> str:
    for threshold, label in SEVERITY_BANDS:
        if cvss >= threshold:
            return label
    return "low"


def fetch_scan_results(task_id: str | None = None) -> list[NormalizedFinding]:
    """
    Trae los resultados del último reporte de un escaneo (o de todas
    las tareas activas si no se especifica task_id) y los normaliza.

    Implementación real esperada (con python-gvm):

        from gvm.connections import TLSConnection
        from gvm.protocols.gmp import Gmp

        with TLSConnection(hostname=OPENVAS_GMP_HOST, port=OPENVAS_GMP_PORT) as conn:
            with Gmp(conn) as gmp:
                gmp.authenticate(OPENVAS_USERNAME, OPENVAS_PASSWORD)
                xml = gmp.get_results(task_id=task_id, filter_string="severity>0")
                # parsear xml y mapear cada <result> a NormalizedFinding

    Se deja sin implementar la conexión real porque requiere la
    librería del sistema (gvm-tools) y acceso de red al servidor GVM
    en AWS, que no existen en este entorno de desarrollo.
    """
    if not OPENVAS_GMP_HOST:
        logger.info("OpenVAS no configurado en este entorno; sync omitido.")
        return []

    logger.warning(
        "fetch_scan_results: conecta python-gvm contra %s:%s para traer resultados reales.",
        OPENVAS_GMP_HOST,
        OPENVAS_GMP_PORT,
    )
    return []


def launch_rescan(task_id: str) -> bool:
    """Dispara un reescaneo (usado por el módulo de verificación)."""
    if not OPENVAS_GMP_HOST:
        logger.info("OpenVAS no configurado; no se puede relanzar el escaneo %s.", task_id)
        return False
    logger.warning("launch_rescan: implementar gmp.start_task(task_id='%s')", task_id)
    return False
