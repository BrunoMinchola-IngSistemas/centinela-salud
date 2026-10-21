"""
Carga el catálogo de controles ISO 27001 curado para salud en todas las
organizaciones (o en una sola con --org "<nombre>").

    python manage.py cargar_catalogo_iso
"""

from django.core.management.base import BaseCommand

from accounts.models import Organization
from controls.services import cargar_catalogo


class Command(BaseCommand):
    help = "Carga el catálogo de controles ISO 27001 seleccionados para salud."

    def add_arguments(self, parser):
        parser.add_argument("--org", help="Nombre exacto de la organización (por defecto: todas).")

    def handle(self, *args, **options):
        orgs = Organization.objects.all()
        if options.get("org"):
            orgs = orgs.filter(name=options["org"])
        for org in orgs:
            controles = cargar_catalogo(org)
            self.stdout.write(self.style.SUCCESS(f"{org.name}: {len(controles)} controles cargados."))
