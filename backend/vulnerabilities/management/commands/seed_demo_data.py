"""
Comando de gestión para poblar datos de demostración, equivalentes a
los del mockup HTML original: una organización, un analista con
clave conocida, activos clínicos, fuentes, controles mapeados a
ISO 27001/HIPAA/CIS, y un puñado de vulnerabilidades realistas con
distintos estados (abierta, en plan, en verificación, cerrada), para
poder abrir la consola y ver algo significativo sin tener que crear
todo a mano con curl.

Uso:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --reset   # borra y vuelve a crear
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from accounts.models import Organization, Role
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality, Exposure
from controls.catalogo_iso import CategoriaHallazgo as Cat
from controls.services import cargar_catalogo
from governance.models import NIVEL_POR_TIPO_ACCION, NivelAutonomia, PoliticaAutonomia, SolicitudAprobacion, TipoAccion
from governance.audit import registrar
from incidents.models import IncidenteReportado
from remediation.models import PlanStatus, RemediationPlan, VerificationAttempt
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource, VulnerabilityStatus

TODAY = date(2026, 9, 20)

# Subconjunto del catálogo CISA Known Exploited Vulnerabilities usado en la demo.
KEV_DEMO = {"CVE-2021-44228", "CVE-2020-1472", "CVE-2017-0144", "CVE-2023-38831"}


class Command(BaseCommand):
    help = "Crea datos de demostración (organización, usuario, activos, controles, vulnerabilidades)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra los datos de demostración existentes (misma organización) antes de crear nuevos.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            org_qs = Organization.objects.filter(name="Clínica San Lucas (demo)")
            if org_qs.exists():
                # Vulnerability.source es PROTECT, así que hay que vaciar las
                # vulnerabilidades antes de poder borrar sus fuentes, y las
                # fuentes antes de poder borrar la organización.
                Vulnerability.objects.filter(organization__in=org_qs).delete()
                VulnerabilitySource.objects.filter(organization__in=org_qs).delete()
                org_qs.delete()
                self.stdout.write("Datos de demostración previos eliminados.")

        org, _ = Organization.objects.get_or_create(
            name="Clínica San Lucas (demo)", defaults={"ruc": "20123456789"}
        )

        demo_users = self._create_users(org)

        assets = self._create_assets(org)
        sources = self._create_sources(org)
        controls = self._create_controls(org)
        self._create_vulnerabilities(org, assets, sources, controls)
        self._create_governance_demo(org)

        self.stdout.write(self.style.SUCCESS("Datos de demostración listos."))
        self.stdout.write(f"  Org:      {org.name} ({org.id})")
        self.stdout.write("  Usuarios (misma clave para todos: demo12345):")
        for username, role_label, token in demo_users:
            self.stdout.write(f"    {username:<18} {role_label:<22} token={token}")

    def _create_users(self, org):
        """
        Tres cuentas con roles distintos sobre la misma organización,
        para poder mostrar casos de uso diferenciados (qué ve un
        analista vs. un administrador vs. el responsable de TI) sin
        tener que crear usuarios a mano cada vez.
        """
        specs = [
            ("demo", Role.ANALYST),
            ("admin_demo", Role.ADMIN),
            ("coordinador_demo", Role.IT_OWNER),
            ("auditor_demo", Role.AUDITOR),
        ]
        created_users = []
        for username, role in specs:
            user, created = User.objects.get_or_create(username=username, defaults={"is_active": True})
            if created or not user.has_usable_password():
                user.set_password("demo12345")
                user.save()
            Profile.objects.update_or_create(user=user, defaults={"organization": org, "role": role})
            token, _ = Token.objects.get_or_create(user=user)
            created_users.append((username, Role(role).label, token.key))
        return created_users

    def _create_assets(self, org):
        specs = [
            ("srv-ehr-01", AssetType.SERVER, "10.10.1.11", "Ubuntu 22.04", Criticality.CRITICAL, True, True),
            ("srv-pacs-01", AssetType.SERVER, "10.10.1.20", "Debian 12", Criticality.CRITICAL, True, True),
            ("dc-01", AssetType.SERVER, "10.10.1.5", "Windows Server 2016", Criticality.CRITICAL, False, True),
            ("srv-backup-01", AssetType.SERVER, "10.10.1.40", "Ubuntu 20.04", Criticality.HIGH, True, True),
            ("portal-pacientes", AssetType.APPLICATION, "10.10.2.8", "nginx 1.24", Criticality.HIGH, True, True),
            ("adm-03", AssetType.WORKSTATION, "10.10.4.33", "Windows 7", Criticality.MEDIUM, True, False),
            ("lab-02", AssetType.WORKSTATION, "10.10.5.12", "Windows 7", Criticality.HIGH, True, False),
            ("bomba-inf-07", AssetType.MEDICAL_DEVICE, "10.10.7.27", "Firmware 3.2", Criticality.CRITICAL, False, False),
        ]
        assets = {}
        for hostname, asset_type, ip, os_name, crit, phi, agent in specs:
            asset, _ = Asset.objects.get_or_create(
                organization=org,
                hostname=hostname,
                defaults={
                    "asset_type": asset_type,
                    "ip_address": ip,
                    "operating_system": os_name,
                    "criticality": crit,
                    "stores_phi": phi,
                    "wazuh_agent_online": agent,
                },
            )
            assets[hostname] = asset

        # Exposición de red (reglas R1-R3). Solo el portal de pacientes
        # está publicado en Internet; el servidor de historias clínicas
        # vive en la DMZ para el acceso de médicos externos.
        exposiciones = {"portal-pacientes": Exposure.INTERNET, "srv-ehr-01": Exposure.PERIMETRAL}
        for hostname, asset in assets.items():
            asset.exposure = exposiciones.get(hostname, Exposure.INTERNA)
            asset.save(update_fields=["exposure"])
        return assets

    def _create_sources(self, org):
        sources = {}
        for source_type, name in [
            (SourceType.OPENVAS, "GVM principal"),
            (SourceType.WAZUH, "Wazuh manager"),
        ]:
            source, _ = VulnerabilitySource.objects.get_or_create(
                organization=org, name=name, defaults={"source_type": source_type}
            )
            sources[source_type] = source
        return sources

    def _create_controls(self, org):
        # Catálogo curado ISO 27001:2022 para salud (ver controls/catalogo_iso.py).
        return cargar_catalogo(org)

    def _create_vulnerabilities(self, org, assets, sources, controls):
        specs = [
            dict(
                external_id="demo-v-1042", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2021-44228", title="Ejecución remota de código en Log4j",
                severity=Severity.CRITICAL, cvss=10.0, epss=0.97, asset="srv-pacs-01", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.OPEN, due_in=-2, priority=98,
                controls=["8.8", "8.9"],
                summary="El servidor PACS usa una versión de Log4j explotable sin autenticación. Existe explotación activa y el equipo almacena imágenes diagnósticas de pacientes.",
                steps=["Aislar el puerto 8080 del PACS desde la red de estaciones.", "Actualizar Log4j a 2.17.1 o superior.", "Reiniciar el servicio y reescanear con OpenVAS."],
            ),
            dict(
                external_id="demo-v-1043", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2020-1472", title="Elevación de privilegios en Netlogon (Zerologon)",
                severity=Severity.CRITICAL, cvss=10.0, epss=0.94, asset="dc-01", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.IN_PLAN, due_in=1, priority=95,
                controls=["5.15", "8.5"],
                summary="El controlador de dominio permite suplantar su cuenta de equipo sin credenciales.",
                steps=["Instalar la actualización de seguridad correspondiente.", "Activar FullSecureChannelProtection.", "Revisar eventos 5827-5829."],
                plan_owner="Diego Ramos (TI)", plan_status=PlanStatus.IN_PROGRESS,
            ),
            dict(
                external_id="demo-v-1046", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2017-0144", title="SMBv1 vulnerable a EternalBlue",
                severity=Severity.HIGH, cvss=8.1, epss=0.96, asset="adm-03", source=SourceType.WAZUH,
                status=VulnerabilityStatus.OPEN, due_in=3, priority=84,
                controls=["8.8", "8.7", "8.22"],
                summary="La estación de admisión mantiene SMBv1 activo en Windows 7, el vector usado por WannaCry.",
                steps=["Deshabilitar SMBv1.", "Aplicar la actualización MS17-010.", "Sustituir el equipo en el próximo ciclo."],
            ),
            dict(
                external_id="demo-v-1049", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2023-38831", title="Ejecución de código en WinRAR",
                severity=Severity.HIGH, cvss=7.8, epss=0.48, asset="lab-02", source=SourceType.WAZUH,
                status=VulnerabilityStatus.IN_VERIFICATION, due_in=14, priority=68,
                controls=["8.7"],
                summary="La versión instalada de WinRAR ejecuta archivos ocultos en comprimidos manipulados.",
                steps=["Actualizar WinRAR a 6.23 o superior.", "Distribuir vía política de software."],
                plan_owner="Lucía Paredes (TI)", plan_status=PlanStatus.IN_VERIFICATION,
            ),
            dict(
                external_id="demo-v-1051", category=Cat.CONFIG_INSEGURA, cve="", title="TLS 1.0 y 1.1 habilitados en el portal de pacientes",
                severity=Severity.MEDIUM, cvss=5.9, epss=0.1, asset="portal-pacientes", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.OPEN, due_in=18, priority=52,
                controls=["8.24"],
                summary="El portal acepta protocolos de cifrado obsoletos que permiten descifrar tráfico bajo ciertas condiciones.",
                steps=["Editar ssl_protocols para permitir solo TLSv1.2 y TLSv1.3.", "Probar con los navegadores usados por pacientes."],
            ),
            dict(
                external_id="demo-v-1030", category=Cat.AUTENTICACION_DEBIL, cve="", title="Credenciales por defecto en bomba de infusión",
                severity=Severity.CRITICAL, cvss=9.8, epss=0.6, asset="bomba-inf-07", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.CLOSED, due_in=None, priority=91,
                controls=["8.5", "8.22"],
                summary="La bomba usaba la contraseña de fábrica, conocida públicamente. Ya corregido.",
                steps=["Cambiar la clave de administración.", "Mover el dispositivo a la VLAN biomédica."],
                plan_owner="Ingeniería biomédica", plan_status=PlanStatus.CLOSED, closed=True,
            ),
        ]

        for spec in specs:
            asset = assets[spec["asset"]]
            source = sources[spec["source"]]
            due_date = TODAY + timedelta(days=spec["due_in"]) if spec.get("due_in") is not None else None

            vuln, _ = Vulnerability.objects.update_or_create(
                organization=org,
                source=source,
                external_id=spec["external_id"],
                defaults={
                    "asset": asset,
                    "cve": spec["cve"],
                    "title": spec["title"],
                    "description": spec["summary"],
                    "severity": spec["severity"],
                    "cvss_score": spec["cvss"],
                    "epss_score": spec["epss"],
                    "priority_score": spec["priority"],
                    "status": spec["status"],
                    "due_date": due_date,
                    "ai_summary": spec["summary"],
                    "ai_remediation_steps": spec["steps"],
                    # CVEs presentes en el catálogo CISA KEV (explotación activa conocida) -> regla R4.
                    "actively_exploited": spec["cve"] in KEV_DEMO,
                    "category": spec["category"],
                },
            )
            # Se suman a los que ya vinculó la categoría (tabla de mapeo 8.5).
            vuln.controls.add(*[controls[code] for code in spec["controls"]])

            if "plan_owner" in spec:
                plan, _ = RemediationPlan.objects.update_or_create(
                    vulnerability=vuln,
                    defaults={
                        "owner_name": spec["plan_owner"],
                        "status": spec["plan_status"],
                        "due_date": due_date or TODAY + timedelta(days=14),
                    },
                )
                if spec.get("closed"):
                    VerificationAttempt.objects.get_or_create(
                        plan=plan,
                        requested_by="Ing. biomédica",
                        defaults={"vulnerability_still_present": False, "scan_reference": "openvas-task-demo"},
                    )

    def _create_governance_demo(self, org):
        """
        HU23/HU27/HU30: siembra la política de autonomía por defecto
        (la misma tabla de NIVEL_POR_TIPO_ACCION), un registro de
        auditoría de ejemplo y un incidente reportado de ejemplo, para
        que las nuevas pantallas de gobernanza no se vean vacías la
        primera vez que se abren.
        """
        for tipo_accion, nivel in NIVEL_POR_TIPO_ACCION.items():
            PoliticaAutonomia.objects.update_or_create(
                organization=org, tipo_accion=tipo_accion, defaults={"nivel": nivel}
            )

        # Un historial corto y realista para que el Registro de auditoría
        # muestre los distintos tipos de decisión (agente vs. personas y
        # las tres modalidades de autonomía).
        for actor, accion, modalidad, objeto_tipo, objeto_id, detalle in [
            ("agente", "analisis_ia", NivelAutonomia.AUTONOMO, "vulnerability", "demo-v-1043",
             {"hallazgo": "Elevación de privilegios en Netlogon (Zerologon)", "prioridad": "critical"}),
            ("demo", "plan_creado", NivelAutonomia.ASISTIDO, "vulnerability", "demo-v-1043",
             {"titulo": "Zerologon en dc-01", "responsable": "Diego Ramos (TI)"}),
            ("agente", "notificacion_enviada", NivelAutonomia.AUTONOMO, "vulnerability", "demo-v-1042",
             {"a": "Responsable de TI", "motivo": "Hallazgo crítico con explotación activa (KEV) en servidor PACS"}),
            ("coordinador_demo", "solicitud_creada", NivelAutonomia.CON_APROBACION, "remediation_plan", "demo-v-1043",
             {"tipo_accion": "modificar_config"}),
        ]:
            registrar(
                organization=org, actor=actor, accion=accion, modalidad=modalidad,
                objeto_tipo=objeto_tipo, objeto_id=objeto_id, detalle=detalle,
            )

        registrar(
            organization=org,
            actor="agente",
            accion="verificacion_cerrada",
            modalidad=NivelAutonomia.AUTONOMO,
            objeto_tipo="vulnerability",
            objeto_id="demo-v-1030",
            detalle={"nota": "Reescaneo confirmó que la vulnerabilidad ya no está presente."},
        )

        # Una solicitud pendiente para que admin_demo pueda probar
        # aprobar/rechazar (HU24).
        plan_dc = RemediationPlan.objects.filter(vulnerability__organization=org, vulnerability__external_id="demo-v-1043").first()
        if plan_dc and not plan_dc.solicitudes_aprobacion.exists():
            SolicitudAprobacion.objects.create(
                plan=plan_dc,
                tipo_accion=TipoAccion.MODIFICAR_CONFIG,
                riesgo_de_no_actuar=(
                    "El controlador de dominio sigue expuesto a Zerologon: un atacante en la red interna "
                    "podría tomar control de todas las cuentas de la clínica, incluidas las del sistema de historias clínicas."
                ),
                efecto_esperado=(
                    "Se activa el modo de cumplimiento de Netlogon (FullSecureChannelProtection). Equipos muy antiguos "
                    "que no soporten canal seguro podrían perder acceso al dominio hasta actualizarlos."
                ),
                plazo=timezone.now() + timedelta(hours=24),
            )

        IncidenteReportado.objects.get_or_create(
            organization=org,
            lugar="Consultorio 3",
            defaults={
                "descripcion": "Laptop desbloqueada con historial clínico de un paciente abierto en pantalla.",
                "ocurrido_en": timezone.make_aware(datetime.combine(TODAY, datetime.min.time())),
                "reportado_por": "demo",
            },
        )
