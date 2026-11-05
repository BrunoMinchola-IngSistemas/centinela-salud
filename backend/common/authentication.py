"""
Las mismas autenticaciones de DRF que ya se usaban (token y sesión),
pero que además activan Row-Level Security en PostgreSQL para el resto
de la petición (ver common/rls.py). En SQLite se comportan igual que
las originales.

El token además expira a las TOKEN_TTL_HORAS horas (DRF no trae
expiración): si alguien copia un token viejo, deja de servir.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .rls import activar_para_usuario


class _RLSMixin:
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            activar_para_usuario(result[0])
        return result


class RLSTokenAuthentication(_RLSMixin, TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if timezone.now() - token.created > timedelta(hours=settings.TOKEN_TTL_HORAS):
            token.delete()
            raise AuthenticationFailed("La sesión expiró. Vuelve a iniciar sesión.")
        return user, token


class RLSSessionAuthentication(_RLSMixin, SessionAuthentication):
    pass
