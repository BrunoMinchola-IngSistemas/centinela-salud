"""
HU26: preguntas en lenguaje natural sobre los datos ya recolectados.

Cómo responde
-------------
1. Reúne los "hechos" de la organización (hallazgos, activos,
   cumplimiento, vencidos, aprobaciones, incidentes) desde la base.
2. Reconoce la intención de la pregunta con reglas en español
   (palabras clave). Cada intención responde SOLO con esos hechos y
   devuelve las fuentes que usó.
3. Si hay un LLM configurado (Qwen en Ollama o Bedrock), se le pasa la
   pregunta junto con los hechos y la instrucción de no inventar; si
   responde "SIN_DATOS" o falla, manda la respuesta por reglas.
4. Si la pregunta no corresponde a ningún dato disponible, lo dice
   explícitamente ("No tengo datos suficientes...") en vez de inventar
   una respuesta no verificada (HU26 esc. 2).
"""

import json
import re
import unicodedata
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from . import qwen

SIN_DATOS = (
    "No tengo datos suficientes para responder eso con la información recolectada. "
    "Puedo responder sobre: hallazgos críticos o abiertos, vencidos, el activo más vulnerable, "
    "el inventario, el cumplimiento ISO 27001, el nivel de riesgo, aprobaciones pendientes, "
    "incidentes reportados, vulnerabilidades explotadas activamente (KEV) o una CVE concreta."
)
NIVEL = {"critical": "crítica", "high": "alta", "medium": "media", "low": "baja", "none": "ninguna", "": "pendiente"}


def _norm(texto):
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def _abiertas(org):
    from vulnerabilities.models import Vulnerability

    return Vulnerability.objects.filter(organization=org).exclude(status="closed").select_related("asset", "plan")


def _r(texto, fuentes):
    return {"respuesta": texto, "datos_suficientes": True, "fuentes": fuentes}


def _lista(vulns, n=3):
    return "; ".join(
        f"{v.cve or 'sin CVE'} «{v.title}» en {v.asset.hostname if v.asset else 'activo pendiente'} (prioridad {NIVEL.get(v.contextual_priority, v.contextual_priority)})"
        for v in vulns[:n]
    )


def _cve(org, p, pregunta):
    from vulnerabilities.models import CatalogoCVE

    m = re.search(r"cve-\d{4}-\d{4,7}", p)
    if not m:
        return None
    cve = m.group(0).upper()
    propias = list(_abiertas(org).filter(cve=cve))
    cat = CatalogoCVE.objects.filter(cve_id=cve).first()
    if not propias and not cat:
        return {"respuesta": f"No tengo datos de {cve}: no aparece en los hallazgos de la clínica ni en la base CVE sincronizada.",
                "datos_suficientes": False, "fuentes": ["vulnerabilidades", "catalogo_cve"]}
    partes = []
    if propias:
        partes.append(f"{cve} afecta a {len(propias)} hallazgo(s) abierto(s): {_lista(propias)}.")
    else:
        partes.append(f"{cve} no aparece en los hallazgos abiertos de la clínica.")
    if cat:
        partes.append(f"En la base CVE: CVSS {cat.cvss_score or 's/d'}{', figura en CISA KEV (explotación activa)' if cat.kev else ''}.")
    return _r(" ".join(partes), ["vulnerabilidades", "catalogo_cve"])


def _criticas(org, p, pregunta):
    if not re.search(r"critic|grave|urgent|peligros", p):
        return None
    vs = list(_abiertas(org).filter(Q(contextual_priority="critical") | Q(severity="critical")).order_by("-priority_score"))
    if not vs:
        return _r("No hay hallazgos críticos abiertos en este momento.", ["vulnerabilidades"])
    return _r(f"Hay {len(vs)} hallazgo(s) crítico(s) abierto(s). Los más prioritarios: {_lista(vs)}.", ["vulnerabilidades"])


def _vencidos(org, p, pregunta):
    if not re.search(r"vencid|atrasad|fuera de plazo|plazo", p):
        return None
    vs = [v for v in _abiertas(org) if v.is_overdue]
    if not vs:
        return _r("No hay hallazgos vencidos: todos los abiertos están dentro de su plazo.", ["vulnerabilidades", "remediacion"])
    return _r(f"Hay {len(vs)} hallazgo(s) vencido(s): {_lista(vs)}.", ["vulnerabilidades", "remediacion"])


def _activo_mas(org, p, pregunta):
    if not (re.search(r"activo|equipo|servidor|maquina", p) and re.search(r"mas|mayor|peor|vulnerable", p)):
        return None
    from assets.models import Asset

    top = (
        Asset.objects.filter(organization=org)
        .annotate(n=Count("vulnerabilities", filter=~Q(vulnerabilities__status="closed")))
        .filter(n__gt=0)
        .order_by("-n")
        .first()
    )
    if not top:
        return _r("Ningún activo tiene hallazgos abiertos.", ["activos", "vulnerabilidades"])
    return _r(
        f"El activo con más hallazgos abiertos es {top.hostname} ({top.get_asset_type_display()}, criticidad "
        f"{NIVEL.get(top.criticality, top.criticality)}{', guarda datos clínicos' if top.stores_phi else ''}) con {top.n}.",
        ["activos", "vulnerabilidades"],
    )


def _inventario(org, p, pregunta):
    if not re.search(r"activo|inventario|equipos|dispositivo", p):
        return None
    from assets.models import Asset

    qs = Asset.objects.filter(organization=org)
    por_tipo = ", ".join(f"{n} {dict(Asset._meta.get_field('asset_type').choices).get(t, t).lower()}" for t, n in
                         qs.values_list("asset_type").annotate(n=Count("id")).values_list("asset_type", "n"))
    phi = qs.filter(stores_phi=True).count()
    return _r(f"El inventario tiene {qs.count()} activos ({por_tipo}); {phi} guardan datos clínicos o personales.", ["activos"])


def _cumplimiento(org, p, pregunta):
    if not re.search(r"cumpl|iso|27001|control|norma|29733", p):
        return None
    from controls.services import cumplimiento_global, cumplimiento_ley_29733, cumplimiento_por_dominio

    dominios = [d for d in cumplimiento_por_dominio(org) if d["controles"]]
    if not dominios:
        return {"respuesta": "No hay controles ISO cargados todavía, así que no puedo calcular el cumplimiento.",
                "datos_suficientes": False, "fuentes": ["controles"]}
    peor = min(dominios, key=lambda d: d["cumplimiento"])
    return _r(
        f"El cumplimiento ISO/IEC 27001 global es {cumplimiento_global(org)} % y el de la Ley 29733 {cumplimiento_ley_29733(org)} %. "
        f"El dominio más débil es {peor['tema']} ({peor['cumplimiento']} %, {peor['pendientes']} controles pendientes).",
        ["controles"],
    )


def _riesgo(org, p, pregunta):
    if not re.search(r"riesgo|score|semaforo|postura|como estamos|estado general|resumen", p):
        return None
    from informes.indicadores import risk_score

    r = risk_score(org)
    return _r(f"Risk Score {r['score']}/100 (semáforo {r['semaforo']}). {r['mensaje']}", ["indicadores"])


def _aprobaciones(org, p, pregunta):
    if not re.search(r"aprob|autoriz|gerencia|escalad", p):
        return None
    from governance.models import SolicitudAprobacion

    qs = SolicitudAprobacion.objects.filter(plan__vulnerability__organization=org, estado__in=["pendiente", "escalada"])
    if not qs.exists():
        return _r("No hay solicitudes de aprobación pendientes.", ["gobernanza"])
    detalle = "; ".join(f"{s.get_tipo_accion_display()} sobre «{s.plan.vulnerability.title}» ({s.get_estado_display().lower()})" for s in qs[:3])
    return _r(f"Hay {qs.count()} solicitud(es) esperando decisión: {detalle}.", ["gobernanza"])


def _incidentes(org, p, pregunta):
    if not re.search(r"incidente|reporte del personal|phishing|sospechos", p):
        return None
    from incidents.models import IncidenteReportado

    qs = IncidenteReportado.objects.filter(organization=org, creado_en__gte=timezone.now() - timedelta(days=30))
    if not qs.exists():
        return _r("No se reportaron incidentes en los últimos 30 días.", ["incidentes"])
    ultimo = qs.order_by("-creado_en").first()
    return _r(
        f"En los últimos 30 días se reportaron {qs.count()} incidente(s). El último: «{ultimo.evaluacion_categoria_display or 'sin evaluar'}» "
        f"en {ultimo.lugar} (severidad {NIVEL.get(ultimo.evaluacion_severidad, ultimo.evaluacion_severidad or 's/d')}).",
        ["incidentes"],
    )


def _kev(org, p, pregunta):
    if not re.search(r"kev|explotad|exploit|activamente", p):
        return None
    vs = list(_abiertas(org).filter(actively_exploited=True))
    if not vs:
        return _r("Ningún hallazgo abierto figura como explotado activamente (CISA KEV).", ["vulnerabilidades", "catalogo_cve"])
    return _r(f"{len(vs)} hallazgo(s) abierto(s) tienen explotación activa reportada: {_lista(vs)}.", ["vulnerabilidades", "catalogo_cve"])


def _abiertas_total(org, p, pregunta):
    if not re.search(r"vulnerab|hallazgo|abiert", p):
        return None
    qs = _abiertas(org)
    por = dict(qs.values_list("contextual_priority").annotate(n=Count("id")).values_list("contextual_priority", "n"))
    detalle = ", ".join(f"{por.get(k, 0)} {NIVEL[k]}" for k in ("critical", "high", "medium", "low"))
    pend = por.get("", 0)
    extra = f" y {pend} pendiente(s) de asociación" if pend else ""
    return _r(f"Hay {qs.count()} hallazgos abiertos: {detalle}{extra}.", ["vulnerabilidades"])


# Orden: de lo más específico a lo más general.
INTENCIONES = [_cve, _kev, _vencidos, _criticas, _activo_mas, _aprobaciones, _incidentes, _cumplimiento, _riesgo,
               _inventario, _abiertas_total]


def por_reglas(org, pregunta):
    p = _norm(pregunta)
    for intencion in INTENCIONES:
        r = intencion(org, p, pregunta)
        if r is not None:
            return r
    return {"respuesta": SIN_DATOS, "datos_suficientes": False, "fuentes": []}


def _hechos(org):
    from informes.indicadores import resumen_ejecutivo

    r = resumen_ejecutivo(org)
    return {
        "riesgo": r["riesgo"],
        "cumplimiento_global": r["cumplimiento_global"],
        "cumplimiento_ley_29733": r["cumplimiento_ley_29733"],
        "por_dominio": r["por_dominio"],
        "principales_riesgos": [x["texto"] for x in r["principales_riesgos"]],
        "vencidos": r["vencidos"],
        "aprobaciones_pendientes": r["aprobaciones_pendientes"],
        "incidentes_30_dias": r["incidentes_30_dias"],
    }


def responder(org, pregunta):
    pregunta = (pregunta or "").strip()[:500]
    base = por_reglas(org, pregunta)
    if qwen.disponible():
        prompt = (
            "Eres el asistente de seguridad de una clínica. Responde en español, en 2-4 frases, usando SOLO los datos "
            "JSON de abajo. Si los datos no permiten responder, responde exactamente SIN_DATOS.\n\n"
            f"DATOS: {json.dumps(_hechos(org), default=str, ensure_ascii=False)}\n"
            f"DATOS_DE_LA_CONSULTA: {json.dumps(base, default=str, ensure_ascii=False)}\n"
            f"PREGUNTA: {pregunta}"
        )
        texto = qwen._call_qwen(prompt).strip()
        if texto and "SIN_DATOS" not in texto:
            return {**base, "respuesta": texto, "datos_suficientes": True, "motor": f"qwen ({qwen.QWEN_PROVIDER})"}
    return {**base, "motor": "reglas"}
