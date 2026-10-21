"""
Demuestra que Row-Level Security funciona: entra como el rol restringido
de la app, fija la organización A y cuenta cuántos hallazgos ve SIN
ningún filtro en la consulta. Debe ver solo los de A, nunca los de otras.

    python manage.py verificar_rls
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from accounts.models import Organization
from common.rls import APP_ROLE


class Command(BaseCommand):
    help = "Comprueba que PostgreSQL aísla los datos por organización (RLS)."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            raise CommandError("Estás usando SQLite. RLS solo existe en PostgreSQL (revisa POSTGRES_DB en .env).")

        orgs = list(Organization.objects.all())
        if not orgs:
            raise CommandError("No hay organizaciones. Corre antes: python manage.py seed_demo_data")

        with connection.cursor() as cur:
            cur.execute("SELECT count(*) FROM vulnerabilities_vulnerability")
            total = cur.fetchone()[0]
            self.stdout.write(f"Como dueño de las tablas (sin RLS): {total} hallazgos en total.")
            ok = True
            for org in orgs:
                cur.execute(f"SET ROLE {APP_ROLE}")
                cur.execute("SELECT set_config('app.current_org', %s, false)", [str(org.id)])
                cur.execute("SELECT count(*), count(DISTINCT organization_id) FROM vulnerabilities_vulnerability")
                visibles, orgs_distintas = cur.fetchone()
                cur.execute("RESET ROLE")
                esperado = org.vulnerabilities.count()
                bien = visibles == esperado and orgs_distintas <= 1
                ok &= bien
                marca = "OK " if bien else "MAL"
                self.stdout.write(f"  [{marca}] Como {APP_ROLE} en '{org.name}': ve {visibles} (esperado {esperado}).")

            cur.execute(f"SET ROLE {APP_ROLE}")
            cur.execute("SELECT set_config('app.current_org', '', false)")
            cur.execute("SELECT count(*) FROM vulnerabilities_vulnerability")
            sin_org = cur.fetchone()[0]
            cur.execute("RESET ROLE")
            ok &= sin_org == 0
            self.stdout.write(f"  [{'OK ' if sin_org == 0 else 'MAL'}] Sin organización en sesión: ve {sin_org} (esperado 0).")

            cur.execute(
                "SELECT has_table_privilege(%s, 'governance_registroauditoria', 'UPDATE'),"
                " has_table_privilege(%s, 'governance_registroauditoria', 'DELETE')",
                [APP_ROLE, APP_ROLE],
            )
            puede_upd, puede_del = cur.fetchone()
            ok &= not puede_upd and not puede_del
            self.stdout.write(
                f"  [{'OK ' if not (puede_upd or puede_del) else 'MAL'}] Registro de auditoría: "
                f"UPDATE={'sí' if puede_upd else 'no'}, DELETE={'sí' if puede_del else 'no'} (esperado: no, no)."
            )

        if ok:
            self.stdout.write(self.style.SUCCESS("RLS activo y funcionando."))
        else:
            raise CommandError("Algo no cuadra: revisa la salida de arriba.")
