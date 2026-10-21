"""
Evita escrituras "cruzadas" entre clínicas.

Un campo relacionado de DRF (p. ej. `vulnerability` al crear un plan)
acepta por defecto CUALQUIER id que exista en la base. Eso permitía que
un usuario de la clínica A creara un plan, una solicitud o un hallazgo
apuntando a un registro de la clínica B (bug encontrado en la Ronda 4 al
probar Row-Level Security). Este mixin limita el queryset de cada campo
relacionado editable a la organización del usuario, así un id ajeno se
responde con 400 "objeto no existe", igual que si no existiera.
"""

from rest_framework import serializers


def _filtro_por_organizacion(model, organization):
    nombres = {f.name for f in model._meta.get_fields()}
    if "organization" in nombres:
        return {"organization": organization}
    if "vulnerability" in nombres:  # RemediationPlan
        return {"vulnerability__organization": organization}
    if "plan" in nombres:
        return {"plan__vulnerability__organization": organization}
    return None


class OrganizationScopedRelationsMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        profile = getattr(getattr(request, "user", None), "profile", None)
        for field in self.fields.values():
            rel = field.child_relation if isinstance(field, serializers.ManyRelatedField) else field
            if getattr(rel, "read_only", True) or getattr(rel, "queryset", None) is None:
                continue
            if profile is None:
                rel.queryset = rel.queryset.none()
                continue
            filtro = _filtro_por_organizacion(rel.queryset.model, profile.organization)
            if filtro is not None:
                rel.queryset = rel.queryset.filter(**filtro)
