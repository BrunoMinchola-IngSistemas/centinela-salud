"""
Carga del catálogo ISO, vinculación automática hallazgo -> control
(HU11) y cálculos de cumplimiento (HU12, HU13, HU15, HU16).
"""

from collections import OrderedDict

from .catalogo_iso import ATRIBUTOS, CONTROLES, LEY_29733, MAPEO_CATEGORIA_A_CONTROLES, TEMAS, tema_de
from .models import Control, ControlMapping, EstadoImplementacion, Framework

ORDEN_NIVEL = {"alto": 0, "medio": 1, "bajo": 2}
PESO_ESTADO = {
    EstadoImplementacion.IMPLEMENTADO: 1.0,
    EstadoImplementacion.PARCIAL: 0.5,
    EstadoImplementacion.PENDIENTE: 0.0,
}
DOMINIOS = OrderedDict((clave, etiqueta) for clave, etiqueta in TEMAS.values())


def cargar_catalogo(organization):
    """
    Crea (o actualiza) en la organización los controles del catálogo
    curado para salud. Es idempotente: se puede correr varias veces y
    nunca pisa el estado de implementación que ya marcó la clínica.
    Devuelve {codigo_iso: Control}.
    """
    controles = {}
    for codigo, nombre, base, por_que, otros in CONTROLES:
        madurez, criticidad, costo = ATRIBUTOS.get(codigo, (1, "medio", "medio"))
        control, _ = Control.objects.update_or_create(
            organization=organization,
            iso_code=codigo,
            defaults={
                "name": nombre,
                "theme": tema_de(codigo),
                "baseline_score": base,
                "health_rationale": por_que,
                "madurez_minima": madurez,
                "criticidad": criticidad,
                "costo_estimado": costo,
            },
        )
        ControlMapping.objects.update_or_create(
            control=control, framework=Framework.ISO27001, defaults={"code": f"A.{codigo}"}
        )
        for marco, clave in ((Framework.HIPAA, "hipaa"), (Framework.CIS, "cis")):
            if clave in otros:
                ControlMapping.objects.update_or_create(control=control, framework=marco, defaults={"code": otros[clave]})
        if codigo in LEY_29733:
            ControlMapping.objects.update_or_create(
                control=control, framework=Framework.LEY_29733, defaults={"code": LEY_29733[codigo]}
            )
        controles[codigo] = control
    return controles


def vincular_controles(vulnerability):
    """
    Agrega (sin quitar los que ya tenga) los controles que la tabla de
    mapeo asigna a la categoría del hallazgo. Si la organización aún no
    cargó el catálogo, simplemente no vincula nada.
    """
    codigos = MAPEO_CATEGORIA_A_CONTROLES.get(vulnerability.category, [])
    if not codigos:
        return []
    controles = list(Control.objects.filter(organization=vulnerability.organization, iso_code__in=codigos))
    if controles:
        vulnerability.controls.add(*controles)
    return controles


# --- HU11: brecha pendiente ---------------------------------------------------

def tiene_evidencia(control):
    """Evidencia propia del control o de alguno de sus hallazgos."""
    from evidence.models import Evidence

    return Evidence.objects.filter(control=control).exists() or Evidence.objects.filter(
        vulnerability__controls=control
    ).exists()


def es_brecha_pendiente(control):
    """
    HU11 esc. 2: un control vinculado a hallazgos que no tiene ninguna
    evidencia registrada queda marcado como brecha pendiente.
    """
    return control.vulnerabilities.exists() and not tiene_evidencia(control)


# --- HU13 / HU16: porcentaje de cumplimiento ------------------------------------

def _porcentaje(controles):
    aplicables = [c for c in controles if c.estado_implementacion != EstadoImplementacion.NO_APLICA]
    if not aplicables:
        return None
    return round(100 * sum(PESO_ESTADO[c.estado_implementacion] for c in aplicables) / len(aplicables))


def cumplimiento_por_dominio(organization):
    controles = list(Control.objects.filter(organization=organization))
    filas = []
    for clave, etiqueta in DOMINIOS.items():
        del_dominio = [c for c in controles if c.theme == clave]
        cuenta = {e: sum(1 for c in del_dominio if c.estado_implementacion == e) for e in EstadoImplementacion.values}
        filas.append(
            {
                "dominio": clave,
                "tema": etiqueta,
                "controles": len(del_dominio),
                "implementados": cuenta["implementado"],
                "parciales": cuenta["parcial"],
                "pendientes": cuenta["pendiente"],
                "no_aplica": cuenta["no_aplica"],
                "cumplimiento": _porcentaje(del_dominio) or 0,
            }
        )
    return filas


def cumplimiento_global(organization):
    return _porcentaje(list(Control.objects.filter(organization=organization))) or 0


def cumplimiento_ley_29733(organization):
    controles = list(
        Control.objects.filter(organization=organization, mappings__framework=Framework.LEY_29733).distinct()
    )
    return _porcentaje(controles) or 0


# --- HU12: matriz de controles aplicables según madurez ------------------------

def matriz_aplicables(organization):
    nivel = organization.nivel_madurez
    grupos = []
    for clave, etiqueta in DOMINIOS.items():
        filas = []
        for c in Control.objects.filter(organization=organization, theme=clave).order_by("madurez_minima", "iso_code"):
            if c.madurez_minima <= nivel:
                aplicabilidad = "aplicable"
            elif c.madurez_minima == nivel + 1:
                aplicabilidad = "siguiente_etapa"
            else:
                aplicabilidad = "futuro"
            filas.append(
                {
                    "id": c.id,
                    "codigo": c.iso_code,
                    "nombre": c.name,
                    "madurez_minima": c.madurez_minima,
                    "aplicabilidad": aplicabilidad,
                    "estado": c.estado_implementacion,
                    "criticidad": c.criticidad,
                    "costo": c.costo_estimado,
                }
            )
        grupos.append(
            {
                "dominio": clave,
                "tema": etiqueta,
                "aplicables": sum(1 for f in filas if f["aplicabilidad"] == "aplicable"),
                "controles": filas,
            }
        )
    return {"nivel_madurez": nivel, "nivel_display": organization.get_nivel_madurez_display(), "dominios": grupos}


# --- HU15: recomendaciones ordenadas por criticidad y costo -------------------

ACCION_POR_ESTADO = {
    EstadoImplementacion.PENDIENTE: "Implementar",
    EstadoImplementacion.PARCIAL: "Completar la implementación de",
}


def recomendaciones(organization):
    pendientes = Control.objects.filter(
        organization=organization,
        estado_implementacion__in=[EstadoImplementacion.PENDIENTE, EstadoImplementacion.PARCIAL],
    ).prefetch_related("vulnerabilities")
    filas = []
    for c in pendientes:
        abiertos = c.vulnerabilities.exclude(status="closed").count()
        filas.append(
            {
                "id": c.id,
                "codigo": c.iso_code,
                "nombre": c.name,
                "dominio": c.get_theme_display(),
                "estado": c.get_estado_implementacion_display(),
                "criticidad": c.criticidad,
                "costo": c.costo_estimado,
                "hallazgos_abiertos": abiertos,
                "accion": f"{ACCION_POR_ESTADO[c.estado_implementacion]} el control {c.iso_code} «{c.name}».",
                "motivo": c.health_rationale,
            }
        )
    # Criticidad alta primero; a igual criticidad, el más barato primero;
    # luego el que tiene más hallazgos abiertos.
    filas.sort(key=lambda f: (ORDEN_NIVEL[f["criticidad"]], 2 - ORDEN_NIVEL[f["costo"]], -f["hallazgos_abiertos"], f["codigo"]))
    for i, f in enumerate(filas, start=1):
        f["prioridad"] = i
    return filas
