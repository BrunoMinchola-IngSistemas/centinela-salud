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

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from rest_framework.authtoken.models import Token

from accounts.models import Organization, Role
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality
from controls.models import Control, ControlMapping, Framework
from remediation.models import PlanStatus, RemediationPlan, VerificationAttempt
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource, VulnerabilityStatus

TODAY = date(2026, 9, 20)


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

        user, created = User.objects.get_or_create(username="demo", defaults={"is_active": True})
        if created or not user.has_usable_password():
            user.set_password("demo12345")
            user.save()
        Profile.objects.update_or_create(user=user, defaults={"organization": org, "role": Role.ANALYST})
        token, _ = Token.objects.get_or_create(user=user)

        assets = self._create_assets(org)
        sources = self._create_sources(org)
        controls = self._create_controls(org)
        self._create_vulnerabilities(org, assets, sources, controls)

        self.stdout.write(self.style.SUCCESS("Datos de demostración listos."))
        self.stdout.write(f"  Usuario:  demo / demo12345")
        self.stdout.write(f"  Token:    {token.key}")
        self.stdout.write(f"  Org:      {org.name} ({org.id})")

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
        specs = [
            ("Gestión de vulnerabilidades técnicas", 82, "A.8.8", "§164.308(a)(1)(ii)(A)", "CIS 7"),
            ("Configuración segura de sistemas", 74, "A.8.9", "§164.308(a)(8)", "CIS 4"),
            ("Control de acceso", 79, "A.5.15", "§164.312(a)(1)", "CIS 6"),
            ("Autenticación segura", 68, "A.8.5", "§164.312(d)", "CIS 5"),
            ("Cifrado en tránsito", 77, "A.8.24", "§164.312(e)(1)", "CIS 3"),
            ("Registro y monitoreo", 88, "A.8.15", "§164.312(b)", "CIS 8"),
            ("Protección contra malware", 85, "A.8.7", "§164.308(a)(5)(ii)(B)", "CIS 10"),
            ("Segmentación de redes", 72, "A.8.22", "§164.308(a)(4)", "CIS 12"),
        ]
        controls = {}
        for name, baseline, iso_code, hipaa_code, cis_code in specs:
            control, _ = Control.objects.get_or_create(
                organization=org, name=name, defaults={"baseline_score": baseline}
            )
            for framework, code in [(Framework.ISO27001, iso_code), (Framework.HIPAA, hipaa_code), (Framework.CIS, cis_code)]:
                ControlMapping.objects.get_or_create(control=control, framework=framework, defaults={"code": code})
            controls[name] = control
        return controls

    def _create_vulnerabilities(self, org, assets, sources, controls):
        specs = [
            dict(
                external_id="demo-v-1042", cve="CVE-2021-44228", title="Ejecución remota de código en Log4j",
                severity=Severity.CRITICAL, cvss=10.0, epss=0.97, asset="srv-pacs-01", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.OPEN, due_in=-2, priority=98,
                controls=["Gestión de vulnerabilidades técnicas", "Configuración segura de sistemas"],
                summary="El servidor PACS usa una versión de Log4j explotable sin autenticación. Existe explotación activa y el equipo almacena imágenes diagnósticas de pacientes.",
                steps=["Aislar el puerto 8080 del PACS desde la red de estaciones.", "Actualizar Log4j a 2.17.1 o superior.", "Reiniciar el servicio y reescanear con OpenVAS."],
            ),
            dict(
                external_id="demo-v-1043", cve="CVE-2020-1472", title="Elevación de privilegios en Netlogon (Zerologon)",
                severity=Severity.CRITICAL, cvss=10.0, epss=0.94, asset="dc-01", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.IN_PLAN, due_in=1, priority=95,
                controls=["Control de acceso", "Autenticación segura"],
                summary="El controlador de dominio permite suplantar su cuenta de equipo sin credenciales.",
                steps=["Instalar la actualización de seguridad correspondiente.", "Activar FullSecureChannelProtection.", "Revisar eventos 5827-5829."],
                plan_owner="Diego Ramos (TI)", plan_status=PlanStatus.IN_PROGRESS,
            ),
            dict(
                external_id="demo-v-1046", cve="CVE-2017-0144", title="SMBv1 vulnerable a EternalBlue",
                severity=Severity.HIGH, cvss=8.1, epss=0.96, asset="adm-03", source=SourceType.WAZUH,
                status=VulnerabilityStatus.OPEN, due_in=3, priority=84,
                controls=["Gestión de vulnerabilidades técnicas", "Protección contra malware", "Segmentación de redes"],
                summary="La estación de admisión mantiene SMBv1 activo en Windows 7, el vector usado por WannaCry.",
                steps=["Deshabilitar SMBv1.", "Aplicar la actualización MS17-010.", "Sustituir el equipo en el próximo ciclo."],
            ),
            dict(
                external_id="demo-v-1049", cve="CVE-2023-38831", title="Ejecución de código en WinRAR",
                severity=Severity.HIGH, cvss=7.8, epss=0.48, asset="lab-02", source=SourceType.WAZUH,
                status=VulnerabilityStatus.IN_VERIFICATION, due_in=14, priority=68,
                controls=["Protección contra malware"],
                summary="La versión instalada de WinRAR ejecuta archivos ocultos en comprimidos manipulados.",
                steps=["Actualizar WinRAR a 6.23 o superior.", "Distribuir vía política de software."],
                plan_owner="Lucía Paredes (TI)", plan_status=PlanStatus.IN_VERIFICATION,
            ),
            dict(
                external_id="demo-v-1051", cve="", title="TLS 1.0 y 1.1 habilitados en el portal de pacientes",
                severity=Severity.MEDIUM, cvss=5.9, epss=0.1, asset="portal-pacientes", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.OPEN, due_in=18, priority=52,
                controls=["Cifrado en tránsito"],
                summary="El portal acepta protocolos de cifrado obsoletos que permiten descifrar tráfico bajo ciertas condiciones.",
                steps=["Editar ssl_protocols para permitir solo TLSv1.2 y TLSv1.3.", "Probar con los navegadores usados por pacientes."],
            ),
            dict(
                external_id="demo-v-1030", cve="", title="Credenciales por defecto en bomba de infusión",
                severity=Severity.CRITICAL, cvss=9.8, epss=0.6, asset="bomba-inf-07", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.CLOSED, due_in=None, priority=91,
                controls=["Autenticación segura", "Segmentación de redes"],
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
                },
            )
            vuln.controls.set([controls[name] for name in spec["controls"]])

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
