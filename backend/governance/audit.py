"""
Punto único para escribir en el registro de auditoría (HU27). Cualquier
vista que tome una decisión relevante del agente llama a `registrar()`
en vez de crear un RegistroAuditoria a mano, para que el formato quede
consistente y no se nos olvide ningún campo.
"""

from .models import RegistroAuditoria


def registrar(*, organization, actor, accion, modalidad, objeto_tipo, objeto_id, detalle=None):
    return RegistroAuditoria.objects.create(
        organization=organization,
        actor=actor,
        accion=accion,
        modalidad=modalidad,
        objeto_tipo=objeto_tipo,
        objeto_id=str(objeto_id),
        detalle=detalle or {},
    )
