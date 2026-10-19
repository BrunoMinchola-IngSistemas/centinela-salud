"""
Cliente hacia Qwen corriendo localmente en la sede de la PyME (vía
Ollama o vLLM). La API en AWS llama a este módulo; este módulo es el
único punto que sale por la VPN hacia la red interna de la clínica.

Nada de esto envía datos de pacientes a un servicio de terceros: el
modelo vive dentro de la red del cliente.
"""

import json
import logging
import os
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

QWEN_API_URL = os.getenv("QWEN_API_URL", "http://qwen-local:11434")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5:14b")
REQUEST_TIMEOUT = 30


@dataclass
class VulnerabilityAnalysis:
    summary: str
    steps: list[str] = field(default_factory=list)
    rollback_risk: str = ""
    priority_score: int = 0


@dataclass
class AIAssessment:
    score: int
    recommendation: str


def _call_qwen(prompt: str) -> str:
    """
    Hace la llamada HTTP real al modelo local (API estilo Ollama
    /api/generate). Si el servicio no está disponible -por ejemplo en
    un entorno de desarrollo sin GPU- cae a una respuesta de reserva
    para no romper el flujo del resto de la aplicación.
    """
    try:
        resp = requests.post(
            f"{QWEN_API_URL}/api/generate",
            json={"model": QWEN_MODEL, "prompt": prompt, "stream": False},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except requests.RequestException:
        logger.warning("Qwen local no disponible en %s; usando respuesta de reserva.", QWEN_API_URL)
        return ""


def analyze_vulnerability(vulnerability) -> VulnerabilityAnalysis:
    """
    Arma el prompt con el contexto del hallazgo (CVE, activo, si tiene
    datos de pacientes, etc.) y le pide a Qwen un resumen de riesgo,
    pasos de corrección y el riesgo de aplicar el cambio.

    El prompt real debe pedir salida JSON estructurada; aquí se deja
    el esqueleto de parseo y una reserva legible si el modelo no
    responde en el formato esperado.
    """
    asset = vulnerability.asset
    prompt = (
        "Eres un analista de ciberseguridad para una clínica. Analiza esta vulnerabilidad "
        "y responde en JSON con las claves summary, steps (lista) y rollback_risk.\n\n"
        f"CVE: {vulnerability.cve or 'sin CVE'}\n"
        f"Título: {vulnerability.title}\n"
        f"CVSS: {vulnerability.cvss_score}\n"
        f"Activo: {asset.hostname} ({asset.get_asset_type_display()}, {asset.operating_system})\n"
        f"¿Almacena datos de pacientes?: {'sí' if asset.stores_phi else 'no'}\n"
        f"Criticidad del activo: {asset.get_criticality_display()}\n"
    )
    raw = _call_qwen(prompt)
    try:
        data = json.loads(raw)
        return VulnerabilityAnalysis(
            summary=data.get("summary", ""),
            steps=data.get("steps", []),
            rollback_risk=data.get("rollback_risk", ""),
            priority_score=priority_score(vulnerability),
        )
    except (ValueError, TypeError):
        return VulnerabilityAnalysis(
            summary=(
                "Qwen no está disponible en este entorno. Conecta QWEN_API_URL a la instancia "
                "local para obtener un análisis real de este hallazgo."
            ),
            steps=[],
            rollback_risk="",
            priority_score=priority_score(vulnerability),
        )


def simplify_explanation(vulnerability) -> str:
    prompt = f"Explica en una frase simple, sin jerga técnica, qué significa: {vulnerability.title}"
    return _call_qwen(prompt) or "Análisis no disponible: conecta Qwen local para generar esta explicación."


def clinical_impact(vulnerability) -> str:
    prompt = (
        f"En un párrafo breve, explica el impacto clínico u operativo si se explota: "
        f"{vulnerability.title} en el activo {vulnerability.asset.hostname}."
    )
    return _call_qwen(prompt) or "Análisis no disponible: conecta Qwen local para generar esta explicación."


def suggest_control_improvement(control) -> AIAssessment:
    open_findings = control.vulnerabilities.exclude(status="closed").count()
    prompt = (
        f"El control '{control.name}' tiene {open_findings} hallazgos abiertos relacionados. "
        "Sugiere en 2-3 frases una mejora concreta y accionable para una PyME de salud."
    )
    recommendation = _call_qwen(prompt) or (
        "Análisis no disponible: conecta Qwen local para generar una recomendación basada en los "
        "hallazgos actuales de este control."
    )
    score = max(20, min(99, control.baseline_score - open_findings * 3))
    return AIAssessment(score=score, recommendation=recommendation)


def priority_score(vulnerability) -> int:
    """
    Combina CVSS, EPSS y criticidad del activo en un puntaje 0-100.
    Esta es la heurística de respaldo; en producción Qwen puede
    ajustar este número con contexto adicional (exposición a
    internet, existencia de exploit público, etc.).
    """
    cvss = float(vulnerability.cvss_score or 0)
    epss = float(vulnerability.epss_score or 0)
    crit_weight = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}.get(
        vulnerability.asset.criticality, 0.5
    )
    raw = (cvss / 10 * 55) + (epss * 30) + (crit_weight * 15)
    return round(min(100, max(0, raw)))
