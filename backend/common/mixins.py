"""
Aislamiento por organización (multi-tenant simple): cada PyME ve solo
su propia data. El perfil accounts.User conecta auth.User con una
Organization; este mixin usa esa relación en cada ViewSet que expone
un modelo con FK a Organization, para no repetir el filtro a mano en
cada vista y, sobre todo, para no olvidarlo en ninguna.
"""

from rest_framework.exceptions import PermissionDenied


class OrganizationScopedMixin:
    def _organization(self):
        profile = getattr(self.request.user, "profile", None)
        if profile is None:
            raise PermissionDenied("El usuario no tiene un perfil de organización asociado.")
        return profile.organization

    def get_queryset(self):
        return super().get_queryset().filter(organization=self._organization())

    def perform_create(self, serializer):
        serializer.save(organization=self._organization())
