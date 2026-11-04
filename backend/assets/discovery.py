"""
Descubrimiento de activos tecnológicos.

Dos fuentes:
- `red_local`: barrido de un rango CIDR desde el servidor donde corre
  el backend (ping concurrente + tabla ARP para la MAC + DNS inverso
  para el nombre). Máximo /24 (256 direcciones) por ejecución, para
  que una ejecución no se convierta en un escaneo masivo.
- `wazuh`: inventario de agentes del manager (si está configurado).

El resultado se concilia con el inventario: cada host encontrado se
asocia a un Asset existente (por IP, o por hostname) o crea uno nuevo;
los activos del rango que no respondieron quedan marcados como "sin
señal". Todo queda en un DiscoveryRun (informe) y en auditoría.
"""

import ipaddress
import logging
import platform
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass

from django.db import transaction
from django.utils import timezone

from governance.audit import registrar
from governance.models import NivelAutonomia
from integrations import wazuh

from .models import Asset, AssetType, DiscoveryRun, DiscoveryRunStatus, DiscoverySource

logger = logging.getLogger(__name__)

MAX_HOSTS = 256
PING_TIMEOUT_S = 1
WORKERS = 32


@dataclass
class HostEncontrado:
    ip: str
    hostname: str = ""
    mac: str = ""
    os_name: str = ""
    agent_id: str = ""
    online: bool = True


class ObjetivoInvalido(ValueError):
    pass


def validar_cidr(objetivo: str) -> ipaddress.IPv4Network:
    try:
        red = ipaddress.ip_network(objetivo.strip(), strict=False)
    except ValueError as exc:
        raise ObjetivoInvalido("Indica un rango válido, por ejemplo 192.168.1.0/24.") from exc
    if red.version != 4:
        raise ObjetivoInvalido("Por ahora solo se barren rangos IPv4.")
    if red.num_addresses > MAX_HOSTS:
        raise ObjetivoInvalido(f"El rango es demasiado grande: máximo /24 ({MAX_HOSTS} direcciones) por ejecución.")
    return red


# --- Sondas de red (se reemplazan en las pruebas) ------------------------

def _ping(ip: str) -> bool:
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(PING_TIMEOUT_S * 1000), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(PING_TIMEOUT_S), ip]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=PING_TIMEOUT_S + 2)
    except (subprocess.TimeoutExpired, OSError):
        return False
    # En Windows "Host de destino inaccesible" devuelve código 0, así
    # que hay que mirar que de verdad llegó una respuesta con TTL.
    return out.returncode == 0 and "TTL=" in out.stdout.upper()


def _tabla_arp() -> dict[str, str]:
    """{ip: mac} según la caché ARP del sistema. Vacío si no se puede leer."""
    try:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5).stdout
    except (subprocess.TimeoutExpired, OSError):
        return {}
    tabla = {}
    for linea in out.splitlines():
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)\D+([0-9a-fA-F]{2}([-:])(?:[0-9a-fA-F]{2}\3){4}[0-9a-fA-F]{2})", linea)
        if m:
            tabla[m.group(1)] = m.group(2).replace("-", ":").lower()
    return tabla


def _nombre_dns(ip: str) -> str:
    try:
        socket.setdefaulttimeout(1)
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, OSError):
        return ""


def barrer_red(red: ipaddress.IPv4Network) -> list[HostEncontrado]:
    candidatos = [str(ip) for ip in red.hosts()] or [str(red.network_address)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        vivos = [ip for ip, ok in zip(candidatos, pool.map(_ping, candidatos)) if ok]
    arp = _tabla_arp()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        nombres = list(pool.map(_nombre_dns, vivos))
    return [HostEncontrado(ip=ip, hostname=nombre, mac=arp.get(ip, "")) for ip, nombre in zip(vivos, nombres)]


def agentes_wazuh() -> list[HostEncontrado]:
    return [
        HostEncontrado(ip=a.ip, hostname=a.name, os_name=a.os_name, agent_id=a.agent_id, online=a.online)
        for a in wazuh.fetch_agents()
    ]


# --- Conciliación con el inventario ---------------------------------------

def _conciliar(organization, fuente: str, hosts: list[HostEncontrado], red: ipaddress.IPv4Network | None):
    ahora = timezone.now()
    detalle = []
    nuevos = 0
    vistos_ids = set()

    for host in hosts:
        asset = None
        if host.ip:
            asset = Asset.objects.filter(organization=organization, ip_address=host.ip).first()
        if asset is None and host.hostname:
            asset = Asset.objects.filter(organization=organization, hostname__iexact=host.hostname).first()

        nuevo = asset is None
        if nuevo:
            base = host.hostname or host.ip
            hostname = base
            n = 2
            while Asset.objects.filter(organization=organization, hostname=hostname).exists():
                hostname = f"{base}-{n}"
                n += 1
            asset = Asset(organization=organization, hostname=hostname, asset_type=AssetType.WORKSTATION, discovery_source=fuente)
            nuevos += 1

        if host.ip and not asset.ip_address:
            asset.ip_address = host.ip
        if host.mac:
            asset.mac_address = host.mac
        if host.os_name and not asset.operating_system:
            asset.operating_system = host.os_name
        if host.agent_id:
            asset.wazuh_agent_id = host.agent_id
            asset.wazuh_agent_online = host.online
        asset.reachable = host.online
        asset.last_discovered_at = ahora
        asset.save()
        vistos_ids.add(asset.id)
        detalle.append({**asdict(host), "nuevo": nuevo, "activo_id": str(asset.id), "activo": asset.hostname})

    # Activos del rango barrido que no respondieron: sin señal.
    sin_senal = 0
    if red is not None:
        for asset in Asset.objects.filter(organization=organization, ip_address__isnull=False).exclude(id__in=vistos_ids):
            try:
                if ipaddress.ip_address(asset.ip_address) in red:
                    asset.reachable = False
                    asset.save(update_fields=["reachable"])
                    sin_senal += 1
            except ValueError:
                continue
    return detalle, nuevos, sin_senal


def ejecutar_descubrimiento(*, organization, fuente: str, objetivo: str, actor: str) -> DiscoveryRun:
    red = None
    if fuente == DiscoverySource.RED_LOCAL:
        red = validar_cidr(objetivo)
        objetivo = str(red)
    elif fuente == DiscoverySource.WAZUH:
        objetivo = ""
    else:
        raise ObjetivoInvalido("Fuente de descubrimiento no soportada.")

    run = DiscoveryRun(organization=organization, source=fuente, target=objetivo, started_by=actor)
    try:
        hosts = barrer_red(red) if red is not None else agentes_wazuh()
        with transaction.atomic():
            detalle, nuevos, sin_senal = _conciliar(organization, fuente, hosts, red)
        run.found_count = len(hosts)
        run.new_count = nuevos
        run.unreachable_count = sin_senal
        run.hosts = detalle
        if fuente == DiscoverySource.WAZUH and not hosts and not wazuh.WAZUH_API_URL:
            run.status = DiscoveryRunStatus.ERROR
            run.error = "Wazuh no está configurado en este entorno (WAZUH_API_URL)."
    except Exception as exc:  # noqa: BLE001 - el informe debe guardarse igual
        logger.exception("Fallo en el descubrimiento de activos")
        run.status = DiscoveryRunStatus.ERROR
        run.error = str(exc)
    run.finished_at = timezone.now()
    run.save()

    registrar(
        organization=organization,
        actor=actor,
        accion="descubrimiento_ejecutado",
        modalidad=NivelAutonomia.ASISTIDO,
        objeto_tipo="discovery_run",
        objeto_id=run.id,
        detalle={"fuente": fuente, "objetivo": objetivo, "encontrados": run.found_count, "nuevos": run.new_count, "estado": run.status},
    )
    return run
