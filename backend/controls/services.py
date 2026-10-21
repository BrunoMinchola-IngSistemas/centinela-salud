"""Carga del catálogo ISO y vinculación automática hallazgo -> control (HU11)."""

from .catalogo_iso import CONTROLES, MAPEO_CATEGORIA_A_CONTROLES, tema_de
from .models import Control, ControlMapping, Framework


def cargar_catalogo(organization):
    """
    Crea (o actualiza) en la organización los controles del catálogo
    curado para salud. Es idempotente: se puede correr varias veces.
    Devuelve {codigo_iso: Control}.
    """
    controles = {}
    for codigo, nombre, base, por_que, otros in CONTROLES:
        control, _ = Control.objects.update_or_create(
            organization=organization,
            iso_code=codigo,
            defaults={
                "name": nombre,
                "theme": tema_de(codigo),
                "baseline_score": base,
                "health_rationale": por_que,
            },
        )
        ControlMapping.objects.update_or_create(
            control=control, framework=Framework.ISO27001, defaults={"code": f"A.{codigo}"}
        )
        if "hipaa" in otros:
            ControlMapping.objects.update_or_create(
                control=control, framework=Framework.HIPAA, defaults={"code": otros["hipaa"]}
            )
        if "cis" in otros:
            ControlMapping.objects.update_or_create(
                control=control, framework=Framework.CIS, defaults={"code": otros["cis"]}
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
    controles = list(
        Control.objects.filter(organization=vulnerability.organization, iso_code__in=codigos)
    )
    if controles:
        vulnerability.controls.add(*controles)
    return controles
