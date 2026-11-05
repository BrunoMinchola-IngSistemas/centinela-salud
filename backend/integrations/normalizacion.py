"""
HU04: esquema único de hallazgo.

Cada conector (Wazuh, OpenVAS, Kaspersky, demo) entrega sus datos con
su propio formato; aquí se llevan todos a un mismo diccionario y se
revisa que estén los campos obligatorios. Si falta alguno, el registro
se marca como incompleto y no entra al análisis.
"""

from common.privacidad import seudonimizar_texto

CAMPOS = ["external_id", "asset_hostname", "asset_ip", "title", "description", "severity", "cve", "cvss_score",
          "cvss_vector", "epss_score", "category"]

# Obligatorios del esquema único. "activo" = hostname o IP.
OBLIGATORIOS = {
    "external_id": "Identificador en la fuente",
    "title": "Título del hallazgo",
    "severity": "Severidad (o puntaje CVSS)",
    "activo": "Activo afectado (hostname o IP)",
}

SEVERIDADES = {
    "critical": "critical", "critica": "critical", "crítica": "critical",
    "high": "high", "alta": "high", "medium": "medium", "media": "medium", "moderate": "medium",
    "low": "low", "baja": "low", "info": "low", "log": "low",
}


def _banda(cvss):
    cvss = float(cvss)
    return "critical" if cvss >= 9 else "high" if cvss >= 7 else "medium" if cvss >= 4 else "low"


def normalizar(finding):
    """Acepta un dataclass de cualquier conector o un dict; devuelve el dict del esquema único."""
    origen = finding if isinstance(finding, dict) else vars(finding)
    d = {c: origen.get(c) for c in CAMPOS}
    for c in ("external_id", "asset_hostname", "asset_ip", "title", "description", "cve", "cvss_vector", "category"):
        d[c] = str(d[c] or "").strip()
    sev = SEVERIDADES.get(str(d["severity"] or "").strip().lower(), "")
    if not sev and d["cvss_score"] not in (None, ""):
        try:
            sev = _banda(d["cvss_score"])
        except (TypeError, ValueError):
            sev = ""
    d["severity"] = sev
    # Ley 29733: la descripción que llega de las herramientas puede traer
    # usuarios, correos o DNI; se guarda seudonimizada.
    d["description"] = seudonimizar_texto(d["description"])
    d["title"] = seudonimizar_texto(d["title"])
    return d


def faltantes(d):
    falta = [c for c in ("external_id", "title", "severity") if not d.get(c)]
    if not (d.get("asset_hostname") or d.get("asset_ip")):
        falta.append("activo")
    return falta
