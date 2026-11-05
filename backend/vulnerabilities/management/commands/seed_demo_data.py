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
    python manage.py seed_demo_data --clave "UnaClaveLarga-2026"   # en la nube

En un servidor con DJANGO_DEBUG=False es OBLIGATORIO indicar --clave
(las cuentas demo no pueden quedar con "demo12345" publicadas en Internet).
"""

import random

from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token

from accounts.models import NivelMadurez, Organization, PeriodicidadReporte, Role
from accounts.models import User as Profile
from assets.models import Asset, AssetType, Criticality, Exposure
from controls.catalogo_iso import CategoriaHallazgo as Cat
from controls.models import EstadoImplementacion
from controls.services import cargar_catalogo
from evidence.models import Evidence, EvidenceType
from governance import agente
from incidents.evaluacion import evaluar
from informes.exportar import pdf_bytes
from informes.indicadores import registrar_snapshot
from governance.models import NIVEL_POR_TIPO_ACCION, NivelAutonomia, PoliticaAutonomia, SolicitudAprobacion, TipoAccion
from governance.audit import registrar
from incidents.models import IncidenteReportado
from remediation.models import PlanStatus, RemediationPlan, VerificationAttempt
from vulnerabilities.models import Severity, SourceType, Vulnerability, VulnerabilitySource, VulnerabilityStatus

# Las fechas de la demo se calculan respecto de hoy, para que plazos y
# vencimientos se vean coherentes el día que se presenta.
TODAY = timezone.localdate()
CLAVE_DEMO = "demo12345"

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
        parser.add_argument("--clave", default="", help="Contraseña para las cuentas demo (obligatoria en producción).")

    @transaction.atomic
    def handle(self, *args, **options):
        self.clave = options["clave"] or CLAVE_DEMO
        if not settings.DEBUG and not options["clave"]:
            raise CommandError(
                "Servidor en modo producción (DJANGO_DEBUG=False): indica --clave con una contraseña robusta "
                "para las cuentas demo; no se publican con la clave por defecto."
            )
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
        self._configurar_organizacion(org)

        assets = self._create_assets(org)
        sources = self._create_sources(org)
        controls = self._create_controls(org)
        self._create_vulnerabilities(org, assets, sources, controls)
        self._create_historial(org, assets, sources)
        self._create_governance_demo(org)
        self._create_hu_demo(org, controls)

        self.stdout.write(self.style.SUCCESS("Datos de demostración listos."))
        self.stdout.write(f"  Org:      {org.name} ({org.id})")
        clave = "la indicada con --clave" if options["clave"] else CLAVE_DEMO
        self.stdout.write(f"  Usuarios (misma clave para todos: {clave}):")
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
            ("cumplimiento_demo", Role.COMPLIANCE),
            ("personal_demo", Role.STAFF),
            ("auditor_demo", Role.AUDITOR),
        ]
        created_users = []
        for username, role in specs:
            user, created = User.objects.get_or_create(username=username, defaults={"is_active": True})
            if created or not user.has_usable_password() or self.clave != CLAVE_DEMO:
                user.set_password(self.clave)
                user.save()
            Profile.objects.update_or_create(user=user, defaults={"organization": org, "role": role})
            token, _ = Token.objects.get_or_create(user=user)
            created_users.append((username, Role(role).label, token.key))
        return created_users

    def _configurar_organizacion(self, org):
        """Ajustes que piden HU01 (rango), HU12 (madurez), HU18 (autonomía), HU21 (periodicidad) y HU24 (escalamiento)."""
        org.rango_red = "10.10.1.0/24"
        org.nivel_madurez = NivelMadurez.GESTIONADO
        org.periodicidad_reporte = PeriodicidadReporte.MENSUAL
        org.ejecucion_autonoma_activa = True
        org.responsable_escalamiento = User.objects.filter(username="coordinador_demo").first()
        org.save()

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
        # HU02: al menos 3 fuentes internas de datos.
        for source_type, name in [
            (SourceType.OPENVAS, "GVM principal"),
            (SourceType.WAZUH, "Wazuh manager"),
            (SourceType.KASPERSKY, "Kaspersky Security Center"),
        ]:
            source, _ = VulnerabilitySource.objects.get_or_create(
                organization=org, name=name, defaults={"source_type": source_type}
            )
            sources[source_type] = source
        return sources

    def _create_controls(self, org):
        # Catálogo curado ISO 27001:2022 para salud (ver controls/catalogo_iso.py).
        controles = cargar_catalogo(org)
        # HU13: estado de implementación inicial, derivado del puntaje base
        # (en la clínica real lo marca el Oficial de Cumplimiento).
        for control in controles.values():
            if control.baseline_score >= 80:
                estado = EstadoImplementacion.IMPLEMENTADO
            elif control.baseline_score >= 68:
                estado = EstadoImplementacion.PARCIAL
            else:
                estado = EstadoImplementacion.PENDIENTE
            control.estado_implementacion = estado
            control.estado_actualizado_por = "cumplimiento_demo"
            control.estado_actualizado_en = timezone.now()
            control.save(update_fields=["estado_implementacion", "estado_actualizado_por", "estado_actualizado_en"])
        return controles

    def _create_vulnerabilities(self, org, assets, sources, controls):
        specs = [
            dict(
                external_id="demo-v-1042", vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2021-44228", title="Ejecución remota de código en Log4j",
                severity=Severity.CRITICAL, cvss=10.0, epss=0.97, asset="srv-pacs-01", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.OPEN, due_in=-2, priority=98,
                controls=["8.8", "8.9"],
                summary="El servidor PACS usa una versión de Log4j explotable sin autenticación. Existe explotación activa y el equipo almacena imágenes diagnósticas de pacientes.",
                steps=["Aislar el puerto 8080 del PACS desde la red de estaciones.", "Actualizar Log4j a 2.17.1 o superior.", "Reiniciar el servicio y reescanear con OpenVAS."],
            ),
            dict(
                external_id="demo-v-1043", vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2020-1472", title="Elevación de privilegios en Netlogon (Zerologon)",
                severity=Severity.CRITICAL, cvss=10.0, epss=0.94, asset="dc-01", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.IN_PLAN, due_in=1, priority=95,
                controls=["5.15", "8.5"],
                summary="El controlador de dominio permite suplantar su cuenta de equipo sin credenciales.",
                steps=["Instalar la actualización de seguridad correspondiente.", "Activar FullSecureChannelProtection.", "Revisar eventos 5827-5829."],
                plan_owner="Diego Ramos (TI)", plan_status=PlanStatus.IN_PROGRESS,
            ),
            dict(
                external_id="demo-v-1046", vector="CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2017-0144", title="SMBv1 vulnerable a EternalBlue",
                severity=Severity.HIGH, cvss=8.1, epss=0.96, asset="adm-03", source=SourceType.WAZUH,
                status=VulnerabilityStatus.OPEN, due_in=3, priority=84,
                controls=["8.8", "8.7", "8.22"],
                summary="La estación de admisión mantiene SMBv1 activo en Windows 7, el vector usado por WannaCry.",
                steps=["Deshabilitar SMBv1.", "Aplicar la actualización MS17-010.", "Sustituir el equipo en el próximo ciclo."],
            ),
            dict(
                external_id="demo-v-1049", vector="CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H", category=Cat.SOFTWARE_DESACTUALIZADO, cve="CVE-2023-38831", title="Ejecución de código en WinRAR",
                severity=Severity.HIGH, cvss=7.8, epss=0.48, asset="lab-02", source=SourceType.WAZUH,
                status=VulnerabilityStatus.IN_VERIFICATION, due_in=14, priority=68,
                controls=["8.7"],
                summary="La versión instalada de WinRAR ejecuta archivos ocultos en comprimidos manipulados.",
                steps=["Actualizar WinRAR a 6.23 o superior.", "Distribuir vía política de software."],
                plan_owner="Lucía Paredes (TI)", plan_status=PlanStatus.IN_VERIFICATION,
            ),
            dict(
                external_id="demo-v-1051", vector="CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N", category=Cat.CONFIG_INSEGURA, cve="", title="TLS 1.0 y 1.1 habilitados en el portal de pacientes",
                severity=Severity.MEDIUM, cvss=5.9, epss=0.1, asset="portal-pacientes", source=SourceType.OPENVAS,
                status=VulnerabilityStatus.OPEN, due_in=18, priority=52,
                controls=["8.24"],
                summary="El portal acepta protocolos de cifrado obsoletos que permiten descifrar tráfico bajo ciertas condiciones.",
                steps=["Editar ssl_protocols para permitir solo TLSv1.2 y TLSv1.3.", "Probar con los navegadores usados por pacientes."],
            ),
            dict(
                external_id="demo-v-1030", vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", category=Cat.AUTENTICACION_DEBIL, cve="", title="Credenciales por defecto en bomba de infusión",
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
                    "cvss_vector": spec.get("vector", ""),
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

            if spec.get("closed"):
                vuln.closed_at = timezone.now() - timedelta(days=12)
                vuln.save(update_fields=["closed_at"])

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

    def _create_historial(self, org, assets, sources):
        """
        HU07: un hallazgo sin activo identificable (queda pendiente de asociación).
        HU08/HU10: historial de hallazgos de los últimos 5 meses (mayoría ya
        cerrados) para que la tendencia y el clasificador tengan datos. Son
        datos de DEMOSTRACIÓN generados con semilla fija, no historia real.
        """
        Vulnerability.objects.update_or_create(
            organization=org,
            source=sources[SourceType.OPENVAS],
            external_id="demo-v-1060",
            defaults={
                "asset": None,
                "cve": "",
                "title": "Servicio Telnet abierto en 10.10.9.14 (equipo no identificado)",
                "description": "El escáner encontró Telnet (23/tcp) en una IP que no figura en el inventario.",
                "severity": Severity.HIGH,
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N",
                "category": Cat.ACTIVO_NO_INVENTARIADO,
                "status": VulnerabilityStatus.OPEN,
            },
        )

        rnd = random.Random(2026)
        catalogo = [
            ("Apache HTTP Server desactualizado", Cat.SOFTWARE_DESACTUALIZADO, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"),
            ("OpenSSH con algoritmos débiles", Cat.CONFIG_INSEGURA, "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N"),
            ("Cuenta de usuario inactiva con privilegios", Cat.PRIVILEGIOS_EXCESIVOS, "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N"),
            ("Contraseña sin expiración en servidor", Cat.AUTENTICACION_DEBIL, "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:L/A:N"),
            ("Microsoft Office sin parche de seguridad", Cat.SOFTWARE_DESACTUALIZADO, "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H"),
            ("Registro de eventos deshabilitado", Cat.SIN_REGISTROS, "CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:L/I:N/A:N"),
            ("Cabeceras de seguridad ausentes en aplicación web", Cat.FALLA_APP_WEB, "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N"),
            ("Certificado TLS caducado", Cat.CONFIG_INSEGURA, "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N"),
            ("Java Runtime desactualizado", Cat.SOFTWARE_DESACTUALIZADO, "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:H/I:H/A:H"),
            ("Carpeta compartida con acceso para Todos", Cat.DATOS_CLINICOS_EXPUESTOS, "CVSS:3.1/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:L/A:N"),
        ]
        lista_activos = list(assets.values())
        ahora = timezone.now()
        for i in range(36):
            titulo, categoria, vector = catalogo[i % len(catalogo)]
            asset = lista_activos[rnd.randrange(len(lista_activos))]
            dias_atras = rnd.randint(8, 150)
            cerrada = rnd.random() < 0.75
            v, _ = Vulnerability.objects.update_or_create(
                organization=org,
                source=sources[SourceType.WAZUH if i % 2 else SourceType.OPENVAS],
                external_id=f"hist-{i:03d}",
                defaults={
                    "asset": asset,
                    "title": f"{titulo} ({asset.hostname})",
                    "cvss_vector": vector,
                    "epss_score": round(rnd.random() ** 3, 3),
                    "category": categoria,
                    "severity": Severity.MEDIUM,
                    "status": VulnerabilityStatus.CLOSED if cerrada else VulnerabilityStatus.OPEN,
                },
            )
            detectada = ahora - timedelta(days=dias_atras)
            Vulnerability.objects.filter(pk=v.pk).update(
                first_detected_at=detectada,
                closed_at=detectada + timedelta(days=rnd.randint(3, 40)) if cerrada else None,
            )

    def _create_hu_demo(self, org, controls):
        """Datos de ejemplo de las HU nuevas: acciones del agente, escalamiento, evidencia, ML, vencidos y línea base."""
        from vulnerabilities import ml
        from vulnerabilities.vencimientos import revisar_vencimientos

        # HU18: una acción autónoma ejecutada y una asistida pendiente.
        plan_dc = RemediationPlan.objects.filter(vulnerability__organization=org, vulnerability__external_id="demo-v-1043").first()
        plan_lab = RemediationPlan.objects.filter(vulnerability__organization=org, vulnerability__external_id="demo-v-1049").first()
        if plan_dc and not plan_dc.acciones_agente.exists():
            agente.proponer_accion(plan_dc, TipoAccion.NOTIFICAR, detalle="Aviso del plan en curso.")
        if plan_lab and not plan_lab.acciones_agente.exists():
            agente.proponer_accion(plan_lab, TipoAccion.APLICAR_PARCHE, detalle="Actualizar WinRAR por política.")

        # HU24 esc. 2: una solicitud de alto impacto sin respuesta en plazo -> escalada.
        log4j = Vulnerability.objects.filter(organization=org, external_id="demo-v-1042").first()
        if log4j:
            plan_pacs, _ = RemediationPlan.objects.get_or_create(
                vulnerability=log4j,
                defaults={"owner_name": "coordinador_demo", "due_date": TODAY - timedelta(days=2), "status": PlanStatus.PENDING},
            )
            if not plan_pacs.solicitudes_aprobacion.exists():
                accion = agente.proponer_accion(plan_pacs, TipoAccion.AISLAR_SERVIDOR, detalle="Aislar el PACS mientras se parcha Log4j.")
                SolicitudAprobacion.objects.filter(pk=accion.solicitud_id).update(plazo=timezone.now() - timedelta(hours=1))
                agente.escalar_vencidas()

        # HU14: una evidencia documental con archivo para el control 8.13.
        control = controls.get("8.13")
        if control and not Evidence.objects.filter(organization=org, control=control).exists():
            contenido = pdf_bytes(
                "Acta de prueba de restauración",
                [("titulo", "Acta de prueba de restauración de copias de seguridad"),
                 ("parrafo", f"Fecha: {TODAY:%d/%m/%Y}. Se restauró la base del sistema de historias clínicas en el servidor de "
                             "pruebas en 42 minutos. Resultado: conforme. (Documento de demostración.)")],
            )
            import hashlib

            evidencia = Evidence(
                organization=org, name="Acta de prueba de restauración (demo)", evidence_type=EvidenceType.SIGNED_RECORD,
                control=control, descripcion="Prueba trimestral de restauración.", nombre_original="acta_restauracion.pdf",
                tamano_bytes=len(contenido), sha256_hash=hashlib.sha256(contenido).hexdigest(), source_system="Carga manual",
                created_by="cumplimiento_demo", s3_bucket=getattr(settings, "AWS_STORAGE_BUCKET_NAME", "") or "almacenamiento-local",
            )
            evidencia.archivo.save("acta_restauracion.pdf", ContentFile(contenido), save=False)
            evidencia.s3_key = evidencia.archivo.name
            evidencia.save()

        # HU08: entrenar el clasificador y dejar sugerencias en los abiertos.
        ml.entrenar(org, forzar=True)
        for v in Vulnerability.objects.filter(organization=org, asset__isnull=False).exclude(status=VulnerabilityStatus.CLOSED):
            ml.clasificar(v)

        # HU22: avisa los críticos vencidos. HU20: línea base del Risk Score.
        revisar_vencimientos()
        registrar_snapshot(org)

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

        descripcion = "Laptop desbloqueada con historial clínico de un paciente abierto en pantalla."
        evaluacion = evaluar(descripcion, "Consultorio 3")
        IncidenteReportado.objects.get_or_create(
            organization=org,
            lugar="Consultorio 3",
            defaults={
                "descripcion": descripcion,
                "ocurrido_en": timezone.make_aware(datetime.combine(TODAY, datetime.min.time())),
                "reportado_por": "personal_demo",
                "evaluacion_categoria": evaluacion["categoria"],
                "evaluacion_severidad": evaluacion["severidad"],
                "evaluacion_resumen": evaluacion["resumen"],
                "evaluacion_recomendacion": evaluacion["recomendacion"],
                "evaluado_en": timezone.now(),
            },
        )
