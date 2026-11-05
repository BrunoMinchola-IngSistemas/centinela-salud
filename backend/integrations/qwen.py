"""
Cliente hacia el modelo de lenguaje Qwen. Tres modos (QWEN_PROVIDER):

- "ollama"  : Qwen en la sede de la PyME (Ollama/vLLM, API /api/generate).
              Los datos no salen de la red de la clínica.
- "bedrock" : Qwen3 servido por Amazon Bedrock en la misma cuenta y
              región de AWS donde corre la consola (rol IAM de la EC2,
              sin claves en el código). QWEN_MODEL = id del modelo en
              Bedrock (verificar en la consola de Bedrock de la región).
- "ninguno" : sin LLM. Todo lo que depende de la IA generativa responde
              con su alternativa determinista (reglas), sin esperar.

Si el proveedor falla, se usa la respuesta de reserva: la consola nunca
se cuelga esperando al modelo (timeouts cortos).
"""

import json
import logging
import os
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

QWEN_PROVIDER = os.getenv("QWEN_PROVIDER", "ollama").strip().lower()
QWEN_API_URL = os.getenv("QWEN_API_URL", "http://qwen-local:11434")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5:14b")
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
REQUEST_TIMEOUT = (3, 60)  # (conexión, lectura) en segundos


def disponible():
    return QWEN_PROVIDER in ("ollama", "bedrock") and (QWEN_PROVIDER == "bedrock" or bool(QWEN_API_URL))


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


def _call_bedrock(prompt: str) -> str:
    import boto3

    cliente = boto3.client("bedrock-runtime", region_name=AWS_REGION)
    resp = cliente.converse(
        modelId=QWEN_MODEL,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 900, "temperature": 0.2},
    )
    return resp["output"]["message"]["content"][0]["text"]


def _call_qwen(prompt: str) -> str:
    """
    Llama al proveedor configurado. Si no hay proveedor o falla,
    devuelve "" y quien llama usa su respuesta de reserva.
    """
    if QWEN_PROVIDER == "ninguno":
        return ""
    try:
        if QWEN_PROVIDER == "bedrock":
            return _call_bedrock(prompt)
        resp = requests.post(
            f"{QWEN_API_URL}/api/generate",
            json={"model": QWEN_MODEL, "prompt": prompt, "stream": False},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception:  # noqa: BLE001 - cualquier fallo del LLM cae a la reserva
        logger.warning("Qwen (%s) no disponible; usando respuesta de reserva.", QWEN_PROVIDER)
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
    activo = (
        f"{asset.hostname} ({asset.get_asset_type_display()}, {asset.operating_system})" if asset else "sin activo asociado"
    )
    prompt = (
        "Eres un analista de ciberseguridad para una clínica. Analiza esta vulnerabilidad "
        "y responde en JSON con las claves summary, steps (lista) y rollback_risk.\n\n"
        f"CVE: {vulnerability.cve or 'sin CVE'}\n"
        f"Título: {vulnerability.title}\n"
        f"CVSS: {vulnerability.cvss_score}\n"
        f"Activo: {activo}\n"
        f"¿Almacena datos de pacientes?: {'sí' if asset and asset.stores_phi else 'no'}\n"
        f"Criticidad del activo: {asset.get_criticality_display() if asset else 'desconocida'}\n"
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
                "El modelo de lenguaje (Qwen) no está disponible en este entorno. Configura QWEN_PROVIDER "
                "(ollama en la sede o bedrock en AWS) para obtener un análisis generado de este hallazgo."
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
        f"{vulnerability.title} en el activo {vulnerability.asset.hostname if vulnerability.asset else 'aún no identificado'}."
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
        vulnerability.asset.criticality if vulnerability.asset else "medium", 0.5
    )
    raw = (cvss / 10 * 55) + (epss * 30) + (crit_weight * 15)
    return round(min(100, max(0, raw)))
