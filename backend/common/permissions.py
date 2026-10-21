"""
Permisos por rol.

Hoy la única regla dura es la del Auditor: "ve todo pero no hace nada".
Puede leer cualquier dato de su organización (GET/HEAD/OPTIONS), pero
cualquier escritura (POST/PUT/PATCH/DELETE, incluidas las acciones como
"analizar", "verificar" o "aprobar") se rechaza con 403.

Se aplica como permiso por defecto de DRF (ver REST_FRAMEWORK en
config/settings.py), así que cubre también las vistas nuevas sin tener
que acordarse de ponerlo en cada una.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import Role

READ_ONLY_ROLES = {Role.AUDITOR}


class IsAuthenticatedRoleAware(BasePermission):
    message = "Tu rol (Auditor) es de solo lectura: puedes ver todo, pero no modificar nada."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        profile = getattr(user, "profile", None)
        if profile is not None and profile.role in READ_ONLY_ROLES:
            return False
        return True
