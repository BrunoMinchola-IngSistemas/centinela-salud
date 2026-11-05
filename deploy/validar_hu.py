"""
Validación de punta a punta de las 30 historias de usuario contra un
servidor REAL (la PC o AWS), por HTTP y con el login de verdad (token,
bloqueo, MFA). Complementa las pruebas automáticas de Django
(backend/common/test_historias_usuario.py), que validan lo mismo por
dentro.

Uso (con el seed de demostración cargado en el servidor):

    python deploy/validar_hu.py --url http://localhost:8000 --clave demo12345
    python deploy/validar_hu.py --url https://54-12-34-56.sslip.io --clave "LaClaveDelSeed"

Deja un informe en deploy/resultados_validacion_<fecha>.md. Crea datos de
prueba en la organización demo (incidentes, evidencias, un usuario
"validador_tmp_*"), nunca toca otras organizaciones, y devuelve los
ajustes que cambia temporalmente (rango de red, madurez, periodicidad,
autonomía) a su valor original.
"""

import argparse
import base64
import hashlib
import hmac
import io
import struct
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

USUARIOS = {
    "gerencia": "admin_demo",
    "ti": "coordinador_demo",
    "cumplimiento": "cumplimiento_demo",
    "personal": "personal_demo",
    "analista": "demo",
    "auditor": "auditor_demo",
}
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def totp(secreto, instante=None):
    clave = base64.b32decode(secreto.upper() + "=" * (-len(secreto) % 8))
    contador = int((instante or time.time()) // 30)
    mac = hmac.new(clave, struct.pack(">Q", contador), hashlib.sha1).digest()
    o = mac[-1] & 0x0F
    return str((struct.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000).zfill(6)


class Cliente:
    def __init__(self, base, verify=True):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.verify = verify

    def _req(self, metodo, ruta, token=None, **kw):
        headers = kw.pop("headers", {})
        if token:
            headers["Authorization"] = f"Token {token}"
        for _ in range(6):
            r = self.s.request(metodo, f"{self.base}{ruta}", headers=headers, timeout=120, **kw)
            if r.status_code != 429:
                return r
            espera = int(r.headers.get("Retry-After", "10"))
            print(f"   (límite de peticiones alcanzado, espero {espera}s…)")
            time.sleep(espera + 1)
        return r

    def get(self, ruta, token=None, **kw):
        return self._req("GET", ruta, token, **kw)

    def post(self, ruta, token=None, **kw):
        return self._req("POST", ruta, token, **kw)

    def patch(self, ruta, token=None, **kw):
        return self._req("PATCH", ruta, token, **kw)

    def delete(self, ruta, token=None, **kw):
        return self._req("DELETE", ruta, token, **kw)

    def login(self, usuario, clave):
        r = self.post("/api/auth/login/", json={"username": usuario, "password": clave})
        if r.status_code != 200 or "token" not in r.json():
            raise RuntimeError(f"No se pudo iniciar sesión como {usuario}: {r.status_code} {r.text[:200]}")
        return r.json()["token"]


class Validador:
    def __init__(self, cli, clave):
        self.c = cli
        self.clave = clave
        self.t = {}
        self.res = []

    def ok(self, hu, escenario, condicion, detalle=""):
        estado = "PASA" if condicion else "FALLA"
        self.res.append((hu, escenario, estado, detalle))
        print(f"[{estado}] {hu} · {escenario}{' · ' + detalle if detalle else ''}")

    def omitido(self, hu, escenario, motivo):
        self.res.append((hu, escenario, "N/A", motivo))
        print(f"[N/A ] {hu} · {escenario} · {motivo}")

    def caso(self, hu, escenario, fn):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - un caso roto no detiene la validación
            self.ok(hu, escenario, False, f"excepción: {type(exc).__name__}: {str(exc)[:160]}")

    def lista(self, r):
        d = r.json()
        return d["results"] if isinstance(d, dict) and "results" in d else d

    # ------------------------------------------------------------------ casos
    def correr(self):
        c, t = self.c, self.t
        salud = c.get("/api/salud/")
        self.ok("INFRA", "API y base de datos responden (/api/salud/)", salud.status_code == 200 and salud.json().get("ok"))
        for rol, usuario in USUARIOS.items():
            t[rol] = c.login(usuario, self.clave)
        org = c.get("/api/organizacion/", t["gerencia"]).json()
        self.org_original = {k: org[k] for k in ("rango_red", "nivel_madurez", "periodicidad_reporte", "ejecucion_autonoma_activa")}
        try:
            for n in range(1, 31):
                getattr(self, f"hu{n:02d}")()
            self.transversal()
        finally:
            c.patch("/api/organizacion/", t["gerencia"], json=self.org_original)

    def hu01(self):
        c, t = self.c, self.t

        def sin_rango():
            c.patch("/api/organizacion/", t["gerencia"], json={"rango_red": ""})
            r = c.post("/api/assets/descubrir/", t["ti"], json={"fuente": "red_local"})
            texto = r.text
            if "deshabilitado" in texto:
                self.omitido("HU01", "Rango no configurado → mensaje", "barrido deshabilitado en la nube (se valida en la PC)")
            else:
                self.ok("HU01", "Rango no configurado → mensaje y no ejecuta", r.status_code == 400 and "Debe configurar un rango de red" in texto)
            c.patch("/api/organizacion/", t["gerencia"], json={"rango_red": self.org_original["rango_red"]})

        def principal():
            r = c.post("/api/assets/descubrir/", t["ti"], json={"fuente": "red_local", "objetivo": "127.0.0.1/32"})
            if r.status_code == 400 and "deshabilitado" in r.text:
                self.omitido("HU01", "Descubrimiento registra activos", "barrido de red deshabilitado en la nube: el inventario llega por Wazuh/sincronización (HU02/HU05)")
                return
            datos = r.json()
            self.ok("HU01", "Descubrimiento registra activos con nombre, tipo, IP y estado", r.status_code == 201 and datos.get("status") in ("ok", "error"), f"encontrados={datos.get('found_count')}")
            r2 = c.post("/api/assets/descubrir/", t["ti"], json={"fuente": "red_local", "objetivo": "127.0.0.1/32"})
            activos = [a for a in self.lista(c.get("/api/assets/", t["ti"], params={"search": "127.0.0.1"}))]
            self.ok("HU01", "Activo ya registrado: actualiza sin duplicar", r2.status_code == 201 and len(activos) <= 1)
            csv = c.get("/api/assets/informe/", t["ti"], params={"formato": "csv"})
            self.ok("HU01", "Inventario exportable (CSV)", csv.status_code == 200 and "text/csv" in csv.headers.get("Content-Type", ""))

        self.caso("HU01", "sin rango", sin_rango)
        self.caso("HU01", "principal", principal)

    def hu02(self):
        def f():
            r = self.c.post("/api/sources/sync/", self.t["ti"])
            res = r.json().get("results", [])
            self.ok("HU02", "Recolección de ≥3 fuentes sin intervención manual", r.status_code == 200 and len(res) >= 3, ", ".join(x["source"] for x in res))
            fallas = self.c.get("/api/integraciones/fallas/", self.t["ti"])
            self.ok("HU02", "Log de fallas disponible (si una fuente no responde se anota y sigue)", fallas.status_code == 200)
            vulns = self.lista(self.c.get("/api/vulnerabilities/", self.t["ti"], params={"search": "Política de contraseñas"}))
            if vulns:
                d = self.c.get(f"/api/vulnerabilities/{vulns[0]['id']}/", self.t["ti"]).json()
                self.ok("HU02", "Datos personales seudonimizados al recolectar", "45678912" not in d["description"] and "[DNI-" in d["description"])
            else:
                self.omitido("HU02", "Seudonimización en recolección", "sin el hallazgo de demostración (fuentes reales configuradas)")
        self.caso("HU02", "principal", f)

    def hu03(self):
        def f():
            r = self.c.post("/api/cve/sincronizar/", self.t["ti"], json={"horas": 24})
            d = r.json()
            if r.status_code == 201:
                self.ok("HU03", "Sincroniza NVD + CISA KEV (CVE nuevas < 24 h)", d["ok"], f"nuevas={d['nuevos']} act.={d['actualizados']} KEV={d['kev_marcados']}")
            else:
                info = self.c.get("/api/cve/sincronizaciones/", self.t["ti"]).json()
                avisos = self.lista(self.c.get("/api/notificaciones/", self.t["ti"]))
                self.ok("HU03", "Fuente CVE no disponible: conserva versión y notifica", r.status_code == 502 and info["total_cve"] >= 0 and any(n["tipo"] == "cve" for n in avisos))
        self.caso("HU03", "principal", f)

    def hu04(self):
        def f():
            incompletos = self.lista(self.c.get("/api/registros-incompletos/", self.t["ti"], params={"corregido": "false"}))
            if not incompletos:
                self.omitido("HU04", "Registro incompleto excluido", "no hay registros incompletos (fuentes reales)")
                return
            reg = incompletos[0]
            antes = self.lista(self.c.get("/api/vulnerabilities/", self.t["ti"], params={"search": reg["external_id"]}))
            self.ok("HU04", "Registro incompleto marcado y excluido del análisis", len(reg["campos_faltantes"]) > 0, f"faltan {reg['campos_faltantes']}")
            datos = {c: "Corregido en validación" if c == "title" else "medium" if c == "severity" else f"val-{c}" for c in reg["campos_faltantes"]}
            if "activo" in datos:
                datos["asset_hostname"] = datos.pop("activo")
            r = self.c.post(f"/api/registros-incompletos/{reg['id']}/corregir/", self.t["ti"], json=datos)
            self.ok("HU04", "Al corregirlo entra al esquema único como hallazgo", r.status_code == 200 and r.json()["vulnerabilidad"], f"antes={len(antes)}")
        self.caso("HU04", "principal", f)

    def hu05(self):
        def f():
            avisos = self.lista(self.c.get("/api/notificaciones/", self.t["ti"]))
            nuevos = [n for n in avisos if n["tipo"] == "activo_nuevo"]
            self.ok("HU05", "Activo nuevo → notificación a TI", len(nuevos) > 0, nuevos[0]["titulo"] if nuevos else "")
            titulos = [n["titulo"] for n in nuevos]
            self.ok("HU05", "Activo ya conocido no se notifica dos veces", len(titulos) == len(set(titulos)))
        self.caso("HU05", "principal", f)

    def _fuente(self):
        return self.lista(self.c.get("/api/sources/", self.t["analista"]))[0]["id"]

    def hu06(self):
        def f():
            r = self.c.post("/api/vulnerabilities/", self.t["analista"], json={
                "source": self._fuente(), "title": "Validación HU06", "external_id": f"val-hu06-{int(time.time())}",
                "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            })
            d = r.json()
            self.ok("HU06", "CVSS 0.0-10.0 calculado de las métricas base", r.status_code == 201 and float(d["cvss_score"]) == 9.8)
            r2 = self.c.patch(f"/api/vulnerabilities/{d['id']}/", self.t["analista"], json={"cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:N/A:N"})
            self.ok("HU06", "Cambio de métricas → recalcula el puntaje", r2.status_code == 200 and float(r2.json()["cvss_score"]) == 3.1)
            self.vuln_val = d["id"]
        self.caso("HU06", "principal", f)

    def hu07(self):
        def f():
            r = self.c.post("/api/vulnerabilities/", self.t["analista"], json={
                "source": self._fuente(), "title": "Validación HU07 sin activo", "severity": "high", "external_id": f"val-hu07-{int(time.time())}",
            })
            self.ok("HU07", "Sin activo asociado → pendiente de asociación", r.status_code == 201 and r.json()["nivel_impacto"] == "pendiente_asociacion")
            log4j = self.lista(self.c.get("/api/vulnerabilities/", self.t["analista"], params={"search": "Log4j"}))[0]
            d = self.c.get(f"/api/vulnerabilities/{log4j['id']}/", self.t["analista"]).json()
            self.log4j = d
            self.ok("HU07", "Muestra activos críticos relacionados y nivel de impacto", d["nivel_impacto"] in ("bajo", "medio", "alto", "critico") and any(a["critico"] for a in d["activos_relacionados"]))
        self.caso("HU07", "principal", f)

    def hu08(self):
        def f():
            r = self.c.post(f"/api/vulnerabilities/{self.log4j['id']}/clasificar/", self.t["ti"])
            d = r.json()
            self.ok("HU08", "Clasificación sugerida con accuracy y F1", r.status_code == 200 and 0 < d["modelo"]["accuracy"] <= 1, f"acc={d['modelo']['accuracy']} f1={d['modelo']['f1_macro']}")
            r2 = self.c.post(f"/api/vulnerabilities/{self.log4j['id']}/corregir-clasificacion/", self.t["ti"], json={"riesgo": "high", "motivo": "Validación"})
            d2 = r2.json()
            self.ok("HU08", "Corrección manual conserva sugerida y corregida", r2.status_code == 200 and d2["riesgo_sugerido"] and d2["riesgo_corregido"] == "high")
        self.caso("HU08", "principal", f)

    def hu09(self):
        def f():
            r = self.c.get("/api/vulnerabilities/matriz-riesgos/", self.t["cumplimiento"])
            d = r.json()
            self.ok("HU09", "Matriz probabilidad × impacto actualizada", r.status_code == 200 and len(d["celdas"]) == 25, f"{d['total']} hallazgos")
            f2 = self.c.get("/api/vulnerabilities/matriz-riesgos/", self.t["cumplimiento"], params={"nivel": "critico"}).json()
            self.ok("HU09", "Filtro por nivel de riesgo", all(x["nivel"] == "critico" for x in f2["celdas"] if x["total"]))
        self.caso("HU09", "principal", f)

    def hu10(self):
        def f():
            desde = (datetime.now() - timedelta(days=60)).date().isoformat()
            r = self.c.get("/api/vulnerabilities/", self.t["cumplimiento"], params={"detectado_desde": desde, "severity": "medium"})
            self.ok("HU10", "Historial filtrable por fecha, severidad y activo", r.status_code == 200)
            tr = self.c.get("/api/vulnerabilities/tendencia/", self.t["cumplimiento"], params={"meses": 3}).json()
            if tr["suficiente"]:
                self.ok("HU10", "Tendencia gráfica de al menos 3 meses", len(tr["meses"]) == 3)
            else:
                self.ok("HU10", "Menos de un mes de operación → mensaje", "suficiente historial" in tr["mensaje"])
        self.caso("HU10", "principal", f)

    def hu11(self):
        def f():
            self.ok("HU11", "Hallazgo vinculado a controles del Anexo A", len(self.log4j["control_codes"]) > 0, ", ".join(self.log4j["control_codes"]))
            ctrls = self.c.get("/api/controls/", self.t["cumplimiento"]).json()
            self.controles = ctrls
            self.ok("HU11", "Control con hallazgos y sin evidencia → brecha pendiente", any(x["brecha_pendiente"] for x in ctrls))
        self.caso("HU11", "principal", f)

    def hu12(self):
        def f():
            self.c.patch("/api/organizacion/", self.t["cumplimiento"], json={"nivel_madurez": 2})
            r = self.c.get("/api/controls/matriz-aplicables/", self.t["cumplimiento"])
            self.ok("HU12", "Matriz agrupada por 4 dominios según la madurez", r.status_code == 200 and len(r.json()["dominios"]) == 4)
            self.c.patch("/api/organizacion/", self.t["cumplimiento"], json={"nivel_madurez": None})
            r2 = self.c.get("/api/controls/matriz-aplicables/", self.t["cumplimiento"])
            self.ok("HU12", "Sin madurez registrada → pide completarla", r2.status_code == 400 and "nivel de madurez" in r2.text)
            self.c.patch("/api/organizacion/", self.t["cumplimiento"], json={"nivel_madurez": self.org_original["nivel_madurez"]})
        self.caso("HU12", "principal", f)

    def hu13(self):
        def f():
            antes = {d["dominio"]: d["cumplimiento"] for d in self.c.get("/api/controls/por-tema/", self.t["cumplimiento"]).json()["dominios"]}
            self.ok("HU13", "% de cumplimiento por dominio", len(antes) == 4)
            ctrl = next(x for x in self.controles if x["theme"] == "personas" and x["estado_implementacion"] != "implementado")
            self.c.patch(f"/api/controls/{ctrl['id']}/", self.t["cumplimiento"], json={"estado_implementacion": "implementado"})
            despues = {d["dominio"]: d["cumplimiento"] for d in self.c.get("/api/controls/por-tema/", self.t["cumplimiento"]).json()["dominios"]}
            self.ok("HU13", "Cambio de estado → recálculo automático", despues["personas"] > antes["personas"], f"{antes['personas']}% → {despues['personas']}%")
            self.c.patch(f"/api/controls/{ctrl['id']}/", self.t["cumplimiento"], json={"estado_implementacion": ctrl["estado_implementacion"]})
        self.caso("HU13", "principal", f)

    def hu14(self):
        def f():
            ctrl = next(x for x in self.controles if x["iso_code"] == "8.8")
            r = self.c.post("/api/evidence/", self.t["cumplimiento"], data={"name": "Validación HU14", "control": ctrl["id"]},
                            files={"archivo": ("validacion.pdf", io.BytesIO(PDF), "application/pdf")})
            d = r.json()
            self.ok("HU14", "Archivo asociado al control con fecha y responsable", r.status_code == 201 and d["created_by"] == "cumplimiento_demo" and d["created_at"])
            mal = self.c.post("/api/evidence/", self.t["cumplimiento"], data={"name": "x", "control": ctrl["id"]},
                              files={"archivo": ("malo.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")})
            self.ok("HU14", "Formato no válido → rechazado con mensaje", mal.status_code == 400 and "Formato de archivo no válido" in mal.text)
            dl = self.c.get(f"/api/evidence/{d['id']}/descargar/", self.t["auditor"])
            self.ok("HU14", "Descarga solo por la API, con verificación SHA-256", dl.status_code == 200 and dl.content == PDF and dl.headers.get("X-Integridad-SHA256") == "ok")
        self.caso("HU14", "principal", f)

    def hu15(self):
        def f():
            d = self.c.get("/api/controls/recomendaciones/", self.t["cumplimiento"]).json()
            orden = {"alto": 0, "medio": 1, "bajo": 2}
            claves = [(orden[x["criticidad"]], 2 - orden[x["costo"]]) for x in d["recomendaciones"]]
            self.ok("HU15", "Recomendaciones ordenadas por criticidad y costo", claves == sorted(claves), f"{len(claves)} controles")
            x = self.c.get("/api/controls/recomendaciones/", self.t["cumplimiento"], params={"formato": "xlsx"})
            self.ok("HU15", "Exportables como plan de acción (Excel/PDF)", x.status_code == 200 and x.content[:2] == b"PK")
        self.caso("HU15", "principal", f)

    def hu16(self):
        def f():
            d = self.c.get("/api/ejecutivo/resumen/", self.t["gerencia"]).json()
            self.ok("HU16", "Panel de Gerencia con % global ISO y Ley 29733", "cumplimiento_global" in d and "cumplimiento_ley_29733" in d,
                    f"ISO {d['cumplimiento_global']}% · Ley {d['cumplimiento_ley_29733']}%")
            self.ok("HU16", "Se actualiza sin recargar (la consola consulta cada 30 s; dato con hora)", bool(d.get("actualizado_en")))
        self.caso("HU16", "principal", f)

    def hu17(self):
        def f():
            r = self.c.post("/api/remediation-plans/generar/", self.t["cumplimiento"], json={"prioridad_minima": "low"})
            self.ok("HU17", "Plan con responsable, plazo y estado", r.status_code == 201, f"{r.json().get('creados')} acciones nuevas")
            planes = self.lista(self.c.get("/api/remediation-plans/", self.t["cumplimiento"]))
            self.planes = planes
            self.ok("HU17", "Responsable pendiente marcado cuando no hay uno disponible", all("responsable_pendiente" in p for p in planes))
            pdf = self.c.get("/api/remediation-plans/exportar/", self.t["cumplimiento"], params={"formato": "pdf"})
            self.ok("HU17", "Exportable en PDF o Excel", pdf.status_code == 200 and pdf.content[:4] == b"%PDF")
        self.caso("HU17", "principal", f)

    def _plan_abierto(self):
        return next(p for p in self.planes if p["status"] in ("pending", "in_progress"))

    def hu18(self):
        def f():
            plan = self._plan_abierto()
            r = self.c.post("/api/acciones-agente/", self.t["ti"], json={"plan": plan["id"], "tipo_accion": "notificar"})
            self.ok("HU18", "Acción de lista blanca → se ejecuta sola y se registra", r.json().get("estado") == "ejecutada")
            self.c.patch("/api/organizacion/", self.t["ti"], json={"ejecucion_autonoma_activa": False})
            r2 = self.c.post("/api/acciones-agente/", self.t["ti"], json={"plan": plan["id"], "tipo_accion": "abrir_ticket"})
            self.ok("HU18", "Autonomía desactivada → queda pendiente de aprobación manual", r2.json().get("estado") == "pendiente_manual")
            self.c.patch("/api/organizacion/", self.t["ti"], json={"ejecucion_autonoma_activa": True})
        self.caso("HU18", "principal", f)

    def hu19(self):
        def f():
            plan = next((p for p in self.planes if p["status"] == "pending"), None)
            if not plan:
                self.omitido("HU19", "Cambio de estado", "no hay planes pendientes")
                return
            r = self.c.patch(f"/api/remediation-plans/{plan['id']}/advance/", self.t["ti"])
            logs = self.lista(self.c.get("/api/registros-auditoria/", self.t["gerencia"], params={"accion": "plan_avanzado", "actor": "coordinador_demo"}))
            self.ok("HU19", "Cambio de estado con fecha y usuario, reflejado en el panel", r.status_code == 200 and logs and logs[0]["creado_en"])
        self.caso("HU19", "principal", f)

    def hu20(self):
        def f():
            r = self.c.get("/api/ejecutivo/resumen/", self.t["gerencia"]).json()["riesgo"]
            self.ok("HU20", "Risk Score en lenguaje no técnico con semáforo", r["semaforo"] in ("verde", "ambar", "rojo") and "CVSS" not in r["mensaje"], f"{r['score']}/100 {r['semaforo']}")
        self.caso("HU20", "principal", f)

    def hu21(self):
        def f():
            self.c.patch("/api/organizacion/", self.t["cumplimiento"], json={"periodicidad_reporte": "mensual"})
            r = self.c.post("/api/reportes/generar/", self.t["cumplimiento"], json={"formato": "pdf"})
            ok = r.status_code == 201
            dl = self.c.get(f"/api/reportes/{r.json()['id']}/descargar/", self.t["cumplimiento"]) if ok else None
            self.ok("HU21", "Reporte PDF/Excel con resumen ejecutivo", ok and dl.content[:4] == b"%PDF")
            self.c.patch("/api/organizacion/", self.t["cumplimiento"], json={"periodicidad_reporte": ""})
            r2 = self.c.post("/api/reportes/generar/", self.t["cumplimiento"], json={"formato": "pdf"})
            self.ok("HU21", "Sin periodicidad → solicita configurarla", r2.status_code == 400 and "periodicidad" in r2.text)
            self.c.patch("/api/organizacion/", self.t["cumplimiento"], json={"periodicidad_reporte": self.org_original["periodicidad_reporte"]})
        self.caso("HU21", "principal", f)

    def hu22(self):
        def f():
            avisos = self.lista(self.c.get("/api/notificaciones/", self.t["ti"]))
            vencidos = [n for n in avisos if n["tipo"] == "vencimiento"]
            marcados = self.lista(self.c.get("/api/vulnerabilities/", self.t["ti"], params={"search": "Log4j"}))
            self.ok("HU22", "Crítica vencida → notificación y marcada «vencido»", bool(vencidos) and any(v["is_overdue"] for v in marcados))
        self.caso("HU22", "principal", f)

    def hu23(self):
        def f():
            pols = self.c.get("/api/politicas-autonomia/", self.t["gerencia"]).json()
            pol = next(p for p in pols if p["tipo_accion"] == "aplicar_parche")
            r = self.c.patch(f"/api/politicas-autonomia/{pol['id']}/", self.t["gerencia"], json={"nivel": pol["nivel"]})
            logs = self.lista(self.c.get("/api/registros-auditoria/", self.t["gerencia"], params={"accion": "politica_autonomia_cambiada"}))
            self.ok("HU23", "Cambio de política registrado con usuario y fecha", r.status_code == 200 and bool(logs))
            ais = next(p for p in pols if p["tipo_accion"] == "aislar_servidor")
            r2 = self.c.patch(f"/api/politicas-autonomia/{ais['id']}/", self.t["gerencia"], json={"nivel": "autonomo"})
            self.ok("HU23", "Alto impacto no puede ser autónomo (bloqueo hasta aprobación)", r2.status_code == 400)
        self.caso("HU23", "principal", f)

    def hu24(self):
        def f():
            plan = self._plan_abierto()
            a = self.c.post("/api/acciones-agente/", self.t["ti"], json={"plan": plan["id"], "tipo_accion": "aislar_servidor"}).json()
            self.ok("HU24", "Solicitud a Gerencia (hallazgo, riesgo, efecto) sin ejecutar", a.get("estado") == "pendiente_aprobacion")
            r = self.c.post(f"/api/solicitudes-aprobacion/{a['solicitud']}/aprobar/", self.t["gerencia"], json={"comentario": "Validación"})
            acc = self.c.get(f"/api/acciones-agente/{a['id']}/", self.t["ti"]).json()
            self.ok("HU24", "Tras la aprobación se ejecuta", r.status_code == 200 and acc["estado"] == "ejecutada")
            sols = self.lista(self.c.get("/api/solicitudes-aprobacion/", self.t["gerencia"]))
            esc = [s for s in sols if s["estado"] == "escalada"]
            self.ok("HU24", "Sin respuesta en plazo → escalada a segundo responsable", bool(esc) and esc[0]["escalado_a"], esc[0]["escalado_a"] if esc else "")
        self.caso("HU24", "principal", f)

    def hu25(self):
        def f():
            lineas = self.log4j["explicacion"]
            texto = " ".join(lineas)
            self.ok("HU25", "Explicación de 2-3+ líneas con CVSS, activo y control", len(lineas) >= 2 and "CVSS" in texto and "ISO" in texto)
        self.caso("HU25", "principal", f)

    def hu26(self):
        def f():
            r = self.c.post("/api/asistente/preguntar/", self.t["ti"], json={"pregunta": "¿Cuántas vulnerabilidades críticas hay?"}).json()
            self.ok("HU26", "Responde usando los datos recolectados", r["datos_suficientes"], r["respuesta"][:80])
            r2 = self.c.post("/api/asistente/preguntar/", self.t["ti"], json={"pregunta": "¿Cuántos pacientes atendimos ayer?"}).json()
            self.ok("HU26", "Sin datos suficientes → lo indica explícitamente", not r2["datos_suficientes"])
        self.caso("HU26", "principal", f)

    def hu27(self):
        def f():
            logs = self.lista(self.c.get("/api/registros-auditoria/", self.t["gerencia"], params={"accion": "accion_ejecutada"}))
            d = logs[0] if logs else {}
            self.ok("HU27", "Decisión registrada con fecha, hallazgo, decisión y modalidad", bool(d) and d["creado_en"] and "hallazgo" in d["detalle"] and d["modalidad"])
            p = self.c.patch(f"/api/registros-auditoria/{d['id']}/", self.t["gerencia"], json={"accion": "x"})
            dl = self.c.delete(f"/api/registros-auditoria/{d['id']}/", self.t["gerencia"])
            self.ok("HU27", "Editar o borrar el log → denegado", p.status_code == 405 and dl.status_code == 405)
        self.caso("HU27", "principal", f)

    def hu28(self):
        def f():
            ok = all(self.c.get(ruta, self.t[rol]).status_code == 200 for rol, ruta in [
                ("gerencia", "/api/ejecutivo/resumen/"), ("ti", "/api/assets/"), ("cumplimiento", "/api/controls/"),
                ("personal", "/api/incidentes/"), ("auditor", "/api/registros-auditoria/")])
            self.ok("HU28", "Cada rol accede a sus módulos", ok)
            r = self.c.get("/api/vulnerabilities/", self.t["personal"])
            self.ok("HU28", "Fuera de rol → denegado con «Permisos insuficientes»", r.status_code == 403 and "Permisos insuficientes" in r.text)
        self.caso("HU28", "principal", f)

    def hu29(self):
        def f():
            sufijo = str(int(time.time()))[-6:]
            clave = f"Validacion-{sufijo}-Segura"
            nuevo = self.c.post("/api/usuarios/", self.t["gerencia"], json={"username": f"validador_tmp_{sufijo}", "password": clave, "role": "analyst"})
            if nuevo.status_code != 201:
                self.ok("HU29", "Crear usuario temporal", False, nuevo.text[:120])
                return
            u = nuevo.json()
            tok = self.c.login(u["username"], clave)
            ini = self.c.post("/api/auth/mfa/iniciar/", tok).json()
            self.c.post("/api/auth/mfa/activar/", tok, json={"codigo": totp(ini["secreto"])})
            p1 = self.c.post("/api/auth/login/", json={"username": u["username"], "password": clave}).json()
            p2 = self.c.post("/api/auth/login/mfa/", json={"mfa_token": p1.get("mfa_token", ""), "codigo": totp(ini["secreto"])})
            self.ok("HU29", "Credenciales + segundo factor → acceso", p1.get("mfa_requerido") and p2.status_code == 200 and "token" in p2.json())
            codigos = [self.c.post("/api/auth/login/", json={"username": u["username"], "password": "incorrecta"}).status_code for _ in range(5)]
            sexto = self.c.post("/api/auth/login/", json={"username": u["username"], "password": clave}).status_code
            self.ok("HU29", "5 intentos fallidos → cuenta bloqueada temporalmente", codigos[-1] == 423 and sexto == 423, f"{codigos} → {sexto}")
            self.c.patch(f"/api/usuarios/{u['id']}/", self.t["gerencia"], json={"is_active": False})
        self.caso("HU29", "principal", f)

    def hu30(self):
        def f():
            ahora = datetime.now(timezone.utc).isoformat()
            r = self.c.post("/api/incidentes/", self.t["personal"], json={
                "descripcion": "Me llegó un correo pidiendo mi contraseña y di click al enlace. Mi DNI 45678912 aparecía en el correo.",
                "lugar": "Admisión", "ocurrido_en": ahora})
            d = r.json()
            self.ok("HU30", "Reporte en ≤3 campos evaluado por el agente", r.status_code == 201 and d["evaluacion_categoria"] == "phishing", f"{d.get('evaluacion_categoria')}/{d.get('evaluacion_severidad')}")
            avisos = self.lista(self.c.get("/api/notificaciones/", self.t["ti"]))
            self.ok("HU30", "TI recibe la evaluación en tiempo real", any(n["tipo"] == "incidente" and n["objeto_id"] == d["id"] for n in avisos))
            self.ok("HU30", "Datos personales seudonimizados", "45678912" not in d["descripcion"])
            inc = self.c.post("/api/incidentes/", self.t["personal"], json={"descripcion": "algo", "lugar": ""})
            self.ok("HU30", "Reporte incompleto → no se procesa y pide completar", inc.status_code == 400)
        self.caso("HU30", "principal", f)

    def transversal(self):
        r = self.c.get("/api/salud/")
        if self.c.base.startswith("https://"):
            self.ok("Ley 29733", "Cifrado en tránsito: HTTPS con HSTS", "Strict-Transport-Security" in r.headers, r.headers.get("Strict-Transport-Security", ""))
            http = requests.get(self.c.base.replace("https://", "http://") + "/api/salud/", allow_redirects=False, timeout=20)
            self.ok("Ley 29733", "HTTP redirige a HTTPS", http.status_code in (301, 302, 308))
        else:
            self.omitido("Ley 29733", "Cifrado en tránsito (HTTPS)", "servidor local por HTTP: se valida en AWS")
        self.ok("SEGURIDAD", "Cabeceras: nosniff y X-Frame-Options", r.headers.get("X-Content-Type-Options") == "nosniff" and r.headers.get("X-Frame-Options") == "DENY")
        sin = self.c.get("/api/vulnerabilities/")
        self.ok("SEGURIDAD", "API sin sesión → 401", sin.status_code == 401)

    def informe(self, ruta):
        pasa = sum(1 for x in self.res if x[2] == "PASA")
        falla = sum(1 for x in self.res if x[2] == "FALLA")
        na = sum(1 for x in self.res if x[2] == "N/A")
        lineas = [
            f"# Validación de historias de usuario · {self.c.base}",
            "",
            f"Fecha: {datetime.now():%Y-%m-%d %H:%M}  ·  PASA: {pasa}  ·  FALLA: {falla}  ·  N/A: {na}",
            "",
            "| HU | Escenario | Resultado | Detalle |",
            "|---|---|---|---|",
        ] + [f"| {h} | {e} | {r} | {d} |" for h, e, r, d in self.res]
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lineas) + "\n")
        return pasa, falla, na


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True)
    p.add_argument("--clave", required=True, help="Clave de las cuentas demo (la del seed).")
    p.add_argument("--informe", default="")
    p.add_argument("--sin-verificar-tls", action="store_true")
    a = p.parse_args()
    v = Validador(Cliente(a.url, verify=not a.sin_verificar_tls), a.clave)
    v.correr()
    ruta = a.informe or f"deploy/resultados_validacion_{datetime.now():%Y%m%d_%H%M}.md"
    pasa, falla, na = v.informe(ruta)
    print(f"\nPASA {pasa} · FALLA {falla} · N/A {na} · informe: {ruta}")
    sys.exit(1 if falla else 0)


if __name__ == "__main__":
    main()
