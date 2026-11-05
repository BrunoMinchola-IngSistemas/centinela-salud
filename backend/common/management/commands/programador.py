"""
Programador de tareas del agente (corre como un proceso aparte: el
contenedor "programador" en AWS, o a mano en la PC).

    python manage.py programador             # bucle infinito (revisa cada 60 s)
    python manage.py programador --una-vez   # corre ahora todas las tareas y termina
    python manage.py programador --tarea cve # corre solo una

Tareas y frecuencia:
  recolectar_fuentes   cada 6 h   HU02/HU04/HU05 (Wazuh, OpenVAS, Kaspersky)
  sincronizar_cve      cada 6 h   HU03 (NVD + CISA KEV; < 24 h por CVE)
  revisar_vencimientos cada 15 min HU22
  escalar_solicitudes  cada 5 min  HU24
  reportes_periodicos  cada 1 h   HU21 (genera solo si ya toca)
  foto_de_riesgo       cada 24 h  HU20 / OE3 (línea base y evolución)

Cada tarea guarda su última ejecución en EjecucionTarea, así un
reinicio del contenedor no la repite antes de tiempo. Corre como dueño
de las tablas (sin RLS de usuario) porque recorre todas las clínicas.
"""

import logging
import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from common.models import EjecucionTarea

logger = logging.getLogger("centinela.programador")


def _recolectar():
    from integrations.sync import recolectar_todas

    r = recolectar_todas()
    return f"{sum(len(v) for v in r.values())} fuentes procesadas"


def _cve():
    from vulnerabilities.cve_feed import sincronizar

    s = sincronizar(horas=24)
    return f"ok={s.ok} nuevos={s.nuevos} actualizados={s.actualizados} kev={s.kev_marcados} {s.error[:200]}"


def _vencimientos():
    from vulnerabilities.vencimientos import revisar_vencimientos

    return f"{len(revisar_vencimientos())} vencidos notificados"


def _escalar():
    from governance.agente import escalar_vencidas

    return f"{len(escalar_vencidas())} solicitudes escaladas"


def _reportes():
    from informes.reportes import generar_reportes_periodicos

    return f"{len(generar_reportes_periodicos())} reportes generados"


def _foto():
    from accounts.models import Organization
    from informes.indicadores import registrar_snapshot

    orgs = list(Organization.objects.all())
    for org in orgs:
        registrar_snapshot(org)
    return f"{len(orgs)} organizaciones"


TAREAS = {
    "recolectar_fuentes": (timedelta(hours=6), _recolectar),
    "sincronizar_cve": (timedelta(hours=6), _cve),
    "revisar_vencimientos": (timedelta(minutes=15), _vencimientos),
    "escalar_solicitudes": (timedelta(minutes=5), _escalar),
    "reportes_periodicos": (timedelta(hours=1), _reportes),
    "foto_de_riesgo": (timedelta(hours=24), _foto),
}


def correr(nombre, forzar=False):
    intervalo, funcion = TAREAS[nombre]
    estado, _ = EjecucionTarea.objects.get_or_create(nombre=nombre)
    ahora = timezone.now()
    if not forzar and estado.ultima_ejecucion and ahora - estado.ultima_ejecucion < intervalo:
        return None
    try:
        detalle = funcion()
        estado.ok = True
    except Exception as exc:  # noqa: BLE001 - una tarea que falla no detiene a las demás
        logger.exception("Falló la tarea %s", nombre)
        detalle = f"{type(exc).__name__}: {exc}"
        estado.ok = False
    estado.ultima_ejecucion = ahora
    estado.detalle = detalle[:2000]
    estado.save()
    logger.info("Tarea %s: %s", nombre, detalle)
    return estado


class Command(BaseCommand):
    help = "Ejecuta las tareas periódicas del agente (CVE, recolección, vencimientos, escalamiento, reportes)."

    def add_arguments(self, parser):
        parser.add_argument("--una-vez", action="store_true", help="Corre todas las tareas ahora y termina.")
        parser.add_argument("--tarea", choices=sorted(TAREAS), help="Corre solo esta tarea (forzada).")
        parser.add_argument("--intervalo", type=int, default=60, help="Segundos entre revisiones del bucle.")

    def handle(self, *args, **opciones):
        if opciones["tarea"]:
            e = correr(opciones["tarea"], forzar=True)
            self.stdout.write(f"{opciones['tarea']}: {'OK' if e.ok else 'ERROR'} · {e.detalle}")
            return
        if opciones["una_vez"]:
            for nombre in TAREAS:
                e = correr(nombre, forzar=True)
                self.stdout.write(f"{nombre}: {'OK' if e.ok else 'ERROR'} · {e.detalle}")
            return
        self.stdout.write("Programador de Centinela Salud iniciado.")
        while True:
            close_old_connections()
            for nombre in TAREAS:
                correr(nombre)
            close_old_connections()
            time.sleep(opciones["intervalo"])
