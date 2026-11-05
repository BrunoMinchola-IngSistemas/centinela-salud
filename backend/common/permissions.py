"""
Permisos por rol (permiso por defecto de DRF, ver REST_FRAMEWORK en
config/settings.py), así cubre también las vistas nuevas sin tener que
acordarse de ponerlo en cada una.

Dos reglas:
1. HU28 - módulo: si la vista declara `modulo = "..."` y el rol del
   usuario no tiene ese módulo (common/modulos.py), se responde 403
   "Permisos insuficientes".
2. Auditor "ve todo pero no hace nada": puede leer (GET/HEAD/OPTIONS),
   pero cualquier escritura se rechaza con 403. La única excepción son
   las vistas sobre cosas propias de la persona (su bandeja de
   notificaciones), marcadas con `escritura_propia = True`.
"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role

from .modulos import MODULOS, puede

READ_ONLY_ROLES = {Role.AUDITOR}


class IsAuthenticatedRoleAware(BasePermission):
    message = "Tu rol (Auditor) es de solo lectura: puedes ver todo, pero no modificar nada."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        profile = getattr(user, "profile", None)

        modulo = getattr(view, "modulo", None)
        if modulo and profile is not None and not puede(profile.role, modulo):
            raise PermissionDenied(
                f"Permisos insuficientes: tu rol ({profile.get_role_display()}) no tiene acceso al módulo "
                f"«{MODULOS.get(modulo, modulo)}»."
            )

        if request.method in SAFE_METHODS:
            return True
        if getattr(view, "escritura_propia", False):
            return True
        if profile is not None and profile.role in READ_ONLY_ROLES:
            return False
        return True


def exigir_rol(request, roles, mensaje):
    """Atajo para acciones que solo ciertos roles pueden hacer (p. ej. aprobar)."""
    profile = getattr(request.user, "profile", None)
    if profile is None or profile.role not in roles:
        raise PermissionDenied(mensaje)
    return profile
