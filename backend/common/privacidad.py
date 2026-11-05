"""
Seudonimización de datos personales (Ley N.° 29733, escenarios
"Protección de datos clínicos" de HU02, HU04, HU14, HU27 y HU30).

Qué hace: en los textos libres que el agente guarda (descripción de un
incidente, descripción de un hallazgo que llega de Wazuh/OpenVAS, datos
de un registro incompleto) reemplaza los identificadores de personas
por un seudónimo estable:

    "el paciente con DNI 45678912 escribió desde ana@gmail.com"
 -> "el paciente con DNI [DNI-3f9a1c2b] escribió desde [CORREO-8d02e4aa]"

El seudónimo es un HMAC-SHA256 con una clave secreta propia
(PSEUDONIMIZACION_CLAVE, en AWS guardada en Parameter Store), así que:
- el mismo DNI produce siempre el mismo seudónimo (se puede correlacionar
  "es la misma persona" entre reportes sin ver el dato);
- sin la clave no se puede recalcular ni comprobar un DNI candidato.

Es seudonimización, no anonimización: quien tenga la clave y el dato
original podría comprobar la correspondencia (técnica de "keyed hash"
recomendada por ENISA). El cifrado en reposo (RDS/S3 con KMS) y en
tránsito (HTTPS) lo da la infraestructura, no este módulo.
"""

import hashlib
import hmac
import re

from django.conf import settings

# Orden importa: primero lo más específico.
PATRONES = [
    ("CORREO", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    (
        "HC",
        re.compile(
            r"(?i)\b(?:historia\s+cl[ií]nica|h\.?\s?c\.?)\s*(?:n(?:ro|°|º|\.)?\s*)?[:#]?\s*(\d{3,10})\b"
        ),
    ),
    ("TELEFONO", re.compile(r"(?<![\w-])(?:\+?51[\s-]?)?9\d{2}[\s-]?\d{3}[\s-]?\d{3}(?![\w-])")),
    ("DNI", re.compile(r"(?<![\w.-])\d{8}(?![\w-])")),
]


def _clave():
    return (getattr(settings, "PSEUDONIMIZACION_CLAVE", "") or settings.SECRET_KEY).encode()


def seudonimo(tipo, valor):
    normalizado = re.sub(r"\s|-", "", valor.strip().lower())
    digest = hmac.new(_clave(), f"{tipo}:{normalizado}".encode(), hashlib.sha256).hexdigest()
    return f"[{tipo}-{digest[:8]}]"


def seudonimizar_texto(texto):
    if not texto:
        return texto
    resultado = texto
    for tipo, patron in PATRONES:
        if tipo == "HC":
            # Solo se reemplaza el número, se deja "historia clínica".
            resultado = patron.sub(lambda m: m.group(0).replace(m.group(1), seudonimo(tipo, m.group(1))), resultado)
        else:
            resultado = patron.sub(lambda m, t=tipo: seudonimo(t, m.group(0)), resultado)
    return resultado


def seudonimizar_datos(valor):
    """Aplica seudonimizar_texto a todos los textos de un dict/lista (p. ej. un JSON de origen)."""
    if isinstance(valor, str):
        return seudonimizar_texto(valor)
    if isinstance(valor, dict):
        return {k: seudonimizar_datos(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [seudonimizar_datos(v) for v in valor]
    return valor
