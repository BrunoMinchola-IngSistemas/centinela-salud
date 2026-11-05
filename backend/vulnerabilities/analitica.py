"""
Explicabilidad y analítica de hallazgos:
- HU25: explicación de 2-4 líneas que cita el dato de origen (CVSS,
  activo, reglas aplicadas y control ISO).
- HU09: matriz de riesgos probabilidad x impacto (5 x 5).
- HU10: tendencia mensual de hallazgos detectados y cerrados.
"""

from collections import OrderedDict
from datetime import datetime, timedelta

from django.utils import timezone

from .priority import ETIQUETA

# ---------------------------------------------------------------- HU25

EXPOSICION = {"internet": "expuesto a Internet", "perimetral": "perimetral", "interna": "de red interna"}
CRITICIDAD = {"critical": "crítica", "high": "alta", "medium": "media", "low": "baja"}


def explicacion(v):
    lineas = []
    if v.cvss_score is not None:
        origen = f"vector {v.cvss_vector}" if v.cvss_vector else "puntaje informado por la fuente"
        epss = f" y una probabilidad de explotación (EPSS) de {float(v.epss_score):.0%}" if v.epss_score is not None else ""
        lineas.append(
            f"Severidad técnica {ETIQUETA.get(v.priority_rules.get('nivel_base', v.severity), v.get_severity_display())}: "
            f"CVSS {v.cvss_score} ({origen}){epss}."
        )
    else:
        lineas.append(f"Severidad técnica {v.get_severity_display()} declarada por la fuente ({v.source.get_source_type_display()}), sin CVSS.")

    if v.asset is None:
        lineas.append("No tiene un activo del inventario asociado: queda pendiente de asociación y no se calcula su impacto.")
    else:
        a = v.asset
        datos = ", guarda datos clínicos o personales" if a.stores_phi else ""
        lineas.append(
            f"Afecta a {a.hostname} ({a.get_asset_type_display()}, criticidad {CRITICIDAD.get(a.criticality, a.criticality)}, "
            f"{EXPOSICION.get(a.exposure, a.exposure)}{datos})."
        )
        reglas = [r for r in v.priority_rules.get("reglas", []) if r.get("regla", "").startswith("R")]
        if reglas:
            detalle = "; ".join(f"{r['regla']} ({r['explicacion'].rstrip('.')})" for r in reglas)
            lineas.append(f"Prioridad contextual {ETIQUETA.get(v.contextual_priority, v.contextual_priority)} por {detalle}.")
        else:
            lineas.append(f"Prioridad contextual {ETIQUETA.get(v.contextual_priority, v.contextual_priority)}: ninguna regla de contexto la modificó.")
        if v.actively_exploited:
            lineas.append("La CVE figura en el catálogo CISA KEV (explotación activa reportada).")

    controles = list(v.controls.all())
    if controles:
        orden = sorted(controles, key=lambda c: tuple(int(x) for x in c.iso_code.split(".")) if c.iso_code else (99,))
        nombres = ", ".join(f"{c.iso_code} «{c.name}»" for c in orden)
        lineas.append(
            f"Se vincula a los controles ISO/IEC 27001:2022 {nombres} porque su categoría es «{v.get_category_display()}» "
            "(tabla de mapeo hallazgo→control del OE2, sección 8.5)."
        )
    else:
        lineas.append("Aún no tiene categoría, así que no se vincula a controles ISO; asígnale una para completar el mapeo.")
    return lineas


# ---------------------------------------------------------------- HU09

def probabilidad(v):
    """1 (rara) a 5 (casi segura): EPSS si existe; si no, la exposición del activo. KEV = 5."""
    if v.actively_exploited:
        return 5
    if v.epss_score is not None:
        e = float(v.epss_score)
        p = 1 if e < 0.01 else 2 if e < 0.1 else 3 if e < 0.3 else 4 if e < 0.6 else 5
    else:
        p = {"internet": 3, "perimetral": 2, "interna": 1}.get(v.asset.exposure, 2)
    if v.asset.exposure == "internet":
        p = min(5, p + 1)
    return p


def impacto(v):
    """1 (insignificante) a 5 (catastrófico): criticidad del activo, +1 si guarda datos clínicos."""
    base = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(v.asset.criticality, 2)
    return min(5, base + (1 if v.asset.stores_phi else 0))


def nivel_celda(p, i):
    producto = p * i
    if producto >= 15:
        return "critico"
    if producto >= 10:
        return "alto"
    if producto >= 5:
        return "medio"
    return "bajo"


def matriz_riesgos(queryset, nivel=None):
    abiertas = queryset.exclude(status="closed").select_related("asset")
    celdas = {(p, i): [] for p in range(1, 6) for i in range(1, 6)}
    pendientes = 0
    for v in abiertas:
        if v.asset is None:
            pendientes += 1
            continue
        celdas[(probabilidad(v), impacto(v))].append(v)
    salida = []
    total = 0
    for (p, i), lista in celdas.items():
        n = nivel_celda(p, i)
        if nivel and n != nivel:
            lista = []
        total += len(lista)
        salida.append(
            {
                "probabilidad": p,
                "impacto": i,
                "nivel": n,
                "total": len(lista),
                "hallazgos": [
                    {"id": v.id, "titulo": v.title, "cve": v.cve, "activo": v.asset.hostname, "prioridad": v.contextual_priority}
                    for v in lista
                ],
            }
        )
    return {"celdas": salida, "total": total, "pendientes_asociacion": pendientes, "actualizado_en": timezone.now()}


# ---------------------------------------------------------------- HU10

MIN_DIAS_HISTORIAL = 30


def tendencia(queryset, meses=6):
    ahora = timezone.now()
    primero = queryset.order_by("first_detected_at").values_list("first_detected_at", flat=True).first()
    if primero is None or ahora - primero < timedelta(days=MIN_DIAS_HISTORIAL):
        return {
            "suficiente": False,
            "mensaje": "Aún no hay suficiente historial para graficar la tendencia: se necesita al menos un mes de operación.",
            "meses": [],
        }
    hoy = timezone.localdate()
    claves = OrderedDict()
    anio, mes = hoy.year, hoy.month
    for _ in range(meses):
        claves[(anio, mes)] = {"detectadas": 0, "cerradas": 0}
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
    claves = OrderedDict(reversed(list(claves.items())))
    for detectada, cerrada in queryset.values_list("first_detected_at", "closed_at"):
        d = timezone.localtime(detectada)
        if (d.year, d.month) in claves:
            claves[(d.year, d.month)]["detectadas"] += 1
        if cerrada:
            c = timezone.localtime(cerrada)
            if (c.year, c.month) in claves:
                claves[(c.year, c.month)]["cerradas"] += 1
    # Abiertas al cierre de cada mes = detectadas hasta ese mes - cerradas hasta ese mes.
    filas = []
    for (a, m), datos in claves.items():
        fin = timezone.make_aware(datetime(a + (m == 12), m % 12 + 1, 1))
        abiertas = queryset.filter(first_detected_at__lt=fin).exclude(closed_at__lt=fin).count()
        filas.append({"mes": f"{a}-{m:02d}", **datos, "abiertas_al_cierre": abiertas})
    return {"suficiente": True, "mensaje": "", "meses": filas}
