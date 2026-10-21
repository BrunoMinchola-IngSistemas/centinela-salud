"""
Las mismas autenticaciones de DRF que ya se usaban (token y sesión),
pero que además activan Row-Level Security en PostgreSQL para el resto
de la petición (ver common/rls.py). En SQLite se comportan igual que
las originales.
"""

from rest_framework.authentication import SessionAuthentication, TokenAuthentication

from .rls import activar_para_usuario


class _RLSMixin:
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            activar_para_usuario(result[0])
        return result


class RLSTokenAuthentication(_RLSMixin, TokenAuthentication):
    pass


class RLSSessionAuthentication(_RLSMixin, SessionAuthentication):
    pass
