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

## Ronda 2 — 2026-10-20, 01:00–01:15 (hora de Lima, en vivo con Bruno)

Bruno despertó la consola en su compu y la probó en vivo. Esto salió
de ahí, no de la espera de 8 horas:

**Bug real encontrado apenas se probó en Windows:**
- `.env.example` traía `POSTGRES_DB=centinela` con valor por
  defecto, aunque el comentario decía "déjalas vacías para usar
  SQLite". Al copiarlo a `.env` (paso normal del README), el backend
  intentaba conectarse a PostgreSQL en `localhost:5432` sin clave y
  fallaba en el primer `migrate`. Corregido dejando `POSTGRES_DB=`
  vacío de verdad.

**Hecho:**
- `GET /api/auth/me/` (nuevo): devuelve usuario, rol y la
  organización real de quien inició sesión. Antes la barra superior
  mostraba "Clínica San Lucas" fijo sin importar quién entrara.
- `seed_demo_data` ahora crea 3 cuentas en la misma organización para
  poder mostrar casos de uso distintos: `demo` (analista),
  `admin_demo` (administrador) y `coordinador_demo` (responsable de
  TI) — las tres con clave `demo12345`.
- Manejo de errores del frontend: **antes, 6 de las 8 páginas no
  tenían `.catch` en absoluto** (Assets, Controls, Evidence,
  RemediationPlan, Verification, Vulnerabilities) - un error 403/500
  se veía igual que "no hay datos todavía", que es justo lo que le
  pasó a Bruno con el Panel general apenas entró con un usuario sin
  perfil. Se agregó `src/components/DataState.jsx` (estados de
  carga/error/vacío + `extractErrorMessage`, que interpreta la
  respuesta de axios/DRF) y se aplicó en las 8 páginas, con botón
  "Reintentar".
- Barra superior: ahora muestra el nombre real de la organización, el
  usuario y su rol (`role-badge`), en vez del texto fijo. Si el rol es
  "Administrador" aparece un enlace al admin de Django.
- Estados visuales: spinner de carga, íconos para error/vacío,
  colores consistentes con el resto de la paleta (`--crit`, `--brand`,
  etc.), tanto en claro como en oscuro.
- Login: muestra las 3 cuentas de demo disponibles (con su rol) para
  no tener que recordar cuál usar en cada caso de uso.
- 2 tests nuevos para `/api/auth/me/` (perfil con organización / sin
  perfil → 403). Total: 16 tests, todos verdes. `npm run build` sin
  errores; `npm run lint` (oxlint) sin errores, solo warnings de
  estilo (`set-state-in-effect`, patrón estándar de fetch-on-mount,
  no es un bug).

**Completado justo después (mismo bloque de trabajo), los dos
pendientes que quedaban de Ronda 1:**
- Validación de CVSS (0.0–10.0) y EPSS (0.0–1.0) en
  `VulnerabilityListSerializer` — el modelo no tenía límites de rango
  (un `DecimalField` solo restringe cuántos dígitos acepta, no el
  valor), así que un POST con `cvss_score: 50` se guardaba sin
  problema. 4 tests nuevos en `VulnerabilityValidationTests`.
- Tests de los 3 endpoints de IA (`analyze`, `explain_simple`,
  `clinical_impact`) mockeando `integrations.qwen` con
  `unittest.mock.patch`, para no depender de que Qwen esté corriendo
  ni en desarrollo ni en CI. 3 tests nuevos en `AIEndpointsTests`.
- Total ahora: **23 tests, todos verdes.**

**Pendiente / decisiones para más adelante (no bloqueante):**
- [ ] La diferenciación de roles hoy es solo visual (badge + enlace
  al admin si es "Administrador"); el backend no limita qué puede
  hacer cada rol todavía (todos los perfiles de la misma organización
  ven los mismos datos). Si se quiere permisos reales por rol, es
  trabajo de otra ronda.
- [ ] Decidir con Bruno: ¿PostgreSQL ya, o seguir con SQLite por
  ahora? Ver la guía nueva en el README y en GUIA_RAPIDA.md.
- [ ] Decidir con Bruno: dónde desplegar (hosting gratis/económico
  para la demo de tesis vs. AWS para producción real) — comparación
  entregada en el chat el 20 oct.

## Cómo seguir esto desde cero

```bash
cd backend && source venv/bin/activate
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py runserver
```

En Windows (PowerShell), sin `source`:
```powershell
cd backend
venv\Scripts\activate
python manage.py migrate
python manage.py seed_demo_data --reset
python manage.py runserver
```

```bash
cd frontend
npm install
npm run dev
```

Entrar con `demo` / `demo12345` (analista), `admin_demo` /
`demo12345` (administrador) o `coordinador_demo` / `demo12345`
(responsable de TI).
