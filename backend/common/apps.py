from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _aplicar_rls(sender, using="default", **kwargs):
    from .rls import aplicar_rls

    aplicar_rls(using=using)


class CommonConfig(AppConfig):
    name = "common"

    def ready(self):
        # Después de cada migrate (también en la base de pruebas) se
        # vuelven a aplicar las políticas RLS, así las tablas nuevas
        # nunca quedan sin protección.
        post_migrate.connect(_aplicar_rls, sender=self, dispatch_uid="centinela_aplicar_rls")
