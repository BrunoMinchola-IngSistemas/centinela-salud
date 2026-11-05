"""
Modo demostración de las integraciones (INTEGRACIONES_DEMO=True).

Mientras SaludMedica no dé acceso a su Wazuh/OpenVAS reales, cada
conector que NO esté configurado devuelve este lote fijo de hallazgos
realistas. Así se puede mostrar de punta a punta la recolección
automática de 3 fuentes (HU02), la normalización con un registro
incompleto (HU04), la detección de un activo nuevo (HU05) y la
seudonimización de datos personales. En la consola se indica siempre
que es modo demostración. Con credenciales reales, este módulo no se usa.
"""

DEMO = {
    "openvas": [
        {
            "external_id": "gvm-demo-001", "asset_hostname": "srv-pacs-01", "asset_ip": "10.10.2.15",
            "title": "Apache Log4j2 JNDI RCE (Log4Shell)", "severity": "critical",
            "cve": "CVE-2021-44228", "cvss_score": 10.0, "category": "software_desactualizado",
            "description": "Versión vulnerable de log4j-core detectada en el visor PACS.",
        },
        {
            "external_id": "gvm-demo-002", "asset_hostname": "lab-analizador-02", "asset_ip": "10.10.4.22",
            "title": "SMBv1 habilitado", "severity": "high", "cve": "CVE-2017-0144",
            "cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H", "category": "config_insegura",
            "description": "El equipo del laboratorio acepta SMBv1 (EternalBlue).",
        },
        {
            # Registro incompleto a propósito: el escáner no reportó el título.
            "external_id": "gvm-demo-003", "asset_hostname": "srv-citas-web", "asset_ip": "10.10.1.30",
            "title": "", "severity": "medium", "cve": "",
            "description": "Resultado sin nombre de la prueba (respuesta parcial del escáner).",
        },
    ],
    "wazuh": [
        {
            "external_id": "wazuh-demo-sca-101", "asset_hostname": "admision-pc-07", "asset_ip": "10.10.3.47",
            "title": "Política de contraseñas débil (SCA CIS Windows 10)", "severity": "medium",
            "category": "autenticacion_debil",
            "description": "La cuenta de jperez@saludmedica.pe no exige cambio de clave (DNI del titular 45678912).",
        },
    ],
    "kaspersky": [
        {
            "external_id": "ksc-demo-501", "asset_hostname": "farmacia-pc-02", "asset_ip": "10.10.3.61",
            "title": "Troyano bloqueado: Trojan.Win32.Agent", "severity": "high", "category": "malware",
            "description": "El antivirus bloqueó un adjunto sospechoso abierto por el usuario.",
        },
    ],
}


def hallazgos(tipo_fuente):
    return [dict(h) for h in DEMO.get(tipo_fuente, [])]
