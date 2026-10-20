# Notas de avance — Centinela Salud

Registro de trabajo autónomo mientras Bruno duerme. Cada ronda se
anota aquí: qué se hizo, qué bugs se encontraron y qué queda
pendiente, para que él pueda revisar el progreso sin tener que leer
todo el historial de git.

## Ronda 1 — 2026-10-20, 00:30–02:30 (hora de Lima)

**Hecho:**
- Comando `python manage.py seed_demo_data [--reset]`: crea una
  organización de demo, usuario `demo` / `demo12345`, 8 activos
  clínicos, 2 fuentes (OpenVAS/Wazuh), 8 controles mapeados a
  ISO 27001/HIPAA/CIS, y 6 vulnerabilidades en distintos estados
  (abierta, en plan, en verificación, cerrada) — los mismos datos que
  tenía el mockup HTML original, para que la consola se vea realista
  sin tener que crear todo a mano con curl.
- 14 tests automatizados nuevos (`python manage.py test`):
  - `remediation/tests.py`: ciclo completo crear plan → verificar →
    cerrar + generar evidencia con SHA-256.
  - `vulnerabilities/tests.py`: aislamiento multi-tenant (una
    organización nunca ve los datos de otra, ni por listado ni por id
    directo).
  - `controls/tests.py`: fórmula de cumplimiento (baseline ± 3 por
    hallazgo abierto/cerrado, acotada a [20, 99]).
  - `assets/tests.py`: creación de activos y hostname único por
    organización.
- CI en GitHub Actions (`.github/workflows/ci.yml`): corre los tests
  de Django y el build de Vite en cada push/PR a `main`.

**Bugs reales encontrados y corregidos por los tests (no eran solo
fallas del test, el código tenía el problema):**
1. `remediation/views.py` — `verify()` convertía
   `vulnerability_still_present` con `bool(valor)`. Si el valor
   llegaba como texto desde un formulario (`"false"`), `bool("false")`
   da `True` en Python, así que un reescaneo "negativo" se trataba
   como positivo. Se agregó `_parse_bool()` que interpreta
   correctamente `true/false/1/0/sí/no`, en texto o booleano nativo.
   El frontend actual (axios con JSON) no lo disparaba, pero cualquier
   integración por formulario sí lo habría hecho.
2. `assets/serializers.py` — crear un activo con un hostname
   duplicado en la misma organización reventaba con un
   `IntegrityError` (error 500) en vez de una validación limpia
   (400), porque `organization` no es un campo del serializer (lo
   asigna la vista) y DRF no puede validar automáticamente una
   restricción `UniqueConstraint` que involucra un campo fuera del
   serializer. Se agregó `validate_hostname()` que valida a mano
   contra la organización real del usuario autenticado.
3. `vulnerabilities/management/commands/seed_demo_data.py` (bug
   propio del comando nuevo, no del resto del sistema) — `--reset`
   fallaba porque `Vulnerability.source` es `on_delete=PROTECT`, así
   que no se puede borrar una `Organization` de un tirón mientras
   tenga vulnerabilidades colgando de sus fuentes. Se corrigió el
   orden de borrado (vulnerabilidades → fuentes → organización).

**Pendiente para la próxima ronda (y para cuando Bruno despierte):**
- [ ] Revisar si el formulario de severidad/CVSS necesita más
  validación (p. ej. CVSS fuera de 0–10).
- [ ] Agregar tests para los endpoints de IA (`analyze`,
  `explain_simple`, `clinical_impact`) usando un mock de
  `integrations.qwen` en vez de depender de que Qwen esté disponible.
- [ ] Revisar manejo de errores en el frontend (qué pasa si la API
  devuelve 500/403 en cada página — hoy varias no muestran nada
  claro).
- [ ] Documentar en el README cómo migrar de SQLite a PostgreSQL real
  (las variables ya existen en `.env.example`, falta el paso a paso).
- [ ] Decidir con Bruno: ¿seguimos en SQLite para la tesis o pasamos a
  PostgreSQL esta semana? Es el siguiente tema que él quiere tocar.

## Cómo seguir esto desde cero

```bash
cd backend && source venv/bin/activate
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py runserver
```

```bash
cd frontend
npm install
npm run dev
```

Entrar con `demo` / `demo12345`.
