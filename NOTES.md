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

## Resumen final de esta sesión nocturna (20 oct, ~01:00–02:50 Lima)

Se cubrieron la Ronda 1 completa y la Ronda 2 completa (incluyendo los
2 pendientes que habían quedado para "la próxima ronda"). Estado:
**23 tests automatizados, todos verdes; build y lint del frontend sin
errores; todo subido a GitHub y sincronizado en `D:\Tesis_Obj3`.**

No se programó una Ronda 3 automática. La razón: lo que queda en la
lista de "Próximos pasos sugeridos" del README (conectar OpenVAS/Wazuh
reales, desplegar Qwen, pasar a PostgreSQL, elegir dónde hostear) son
**decisiones que necesitan que Bruno participe** (qué proveedor,
credenciales, si es local o en la nube) — no son pulido de código que
se pueda seguir avanzando solo mientras duerme. Seguir "afinando" sin
una dirección concreta sería inventar trabajo, no ayudar.

Cuando Bruno retome esto, los temas abiertos en orden sugerido son:
1. Revisar lo nuevo en la consola (3 roles de prueba, mensajes de
   error reales, barra superior con datos reales).
2. Decidir hosting para la demo de tesis (comparación en
   `GUIA_RAPIDA.md`, recomendación: Render o Railway).
3. Decidir si pasar a PostgreSQL ahora o seguir con SQLite hasta la
   sustentación (guía paso a paso en `README.md`).
4. Si quiere seguir iterando con Terminal real (no solo clics), usar
   Claude Code en su propia compu — pasos en `GUIA_RAPIDA.md` sección 2.

## Ronda 3 — 2026-10-20, tarde (revisión contra las 30 HU reales de la tesis)

Bruno pidió revisar el documento de contexto completo (`D:\Tesis`, no
`D:\Tesis_Obj3`) para confirmar qué tanto del backlog de 30 HU está
realmente cubierto por el código, y avanzar lo que se pudiera sin
inventar nada que necesite una decisión suya (dataset, proveedor real
de IA, credenciales de Wazuh/OpenVAS reales, etc.).

**Hallazgo honesto:** el código cubre una fracción del backlog real.
Faltaban completo: gobernanza de la remediación (niveles de autonomía,
solicitudes de aprobación), el registro de auditoría inmutable, y el
canal de reporte de incidentes del personal. Esta ronda cierra esas
tres piezas (HU23, HU24, HU27, HU30) de punta a punta — modelo, API,
tests y datos de ejemplo — porque son las que ya estaban completamente
especificadas en el documento de contexto y no dependían de ninguna
decisión pendiente de Bruno.

**Hecho (app nueva `governance`):**
- `PoliticaAutonomia`: qué nivel de autonomía (autónomo / asistido /
  con aprobación gerencial) aplica a cada tipo de acción, por
  organización. Sembrada con la tabla oficial de la sección 8.4 del
  documento (notificar/abrir ticket/desactivar cuenta = autónomo;
  aplicar parche/modificar config = asistido; aislar servidor =
  requiere aprobación).
- `SolicitudAprobacion` (HU24): para una acción que requiere
  aprobación gerencial, el sistema arma una solicitud con el "riesgo
  de no actuar" y el "efecto esperado", y queda pendiente hasta que
  alguien la apruebe o rechace (`POST /api/solicitudes-aprobacion/<id>/aprobar/`
  o `/rechazar/`). Cada decisión queda registrada: quién, cuándo, con
  qué comentario.
- `RegistroAuditoria` (HU27 / RNF-05 "log no editable ni borrable"):
  tabla de **solo inserción**. El ViewSet solo expone list/retrieve/
  create — no hay ninguna ruta de API para editar o borrar un
  registro ya creado (lo verifica un test: PATCH y DELETE devuelven
  405). El modelo además rechaza un segundo `save()` sobre el mismo
  registro, como segunda barrera. (Falta la mitad "motor de base de
  datos" — revocar UPDATE/DELETE a nivel de rol en PostgreSQL — que
  solo tiene sentido aplicar cuando se migre de SQLite a Postgres;
  queda anotado en el docstring del modelo.)
- Un punto único (`governance/audit.py: registrar(...)`) para que
  cualquier vista escriba al log de auditoría sin tener que repetir
  los mismos 6 campos cada vez. Ya se usa en: crear/aprobar/rechazar
  una solicitud de aprobación, y en reportar un incidente.

**Hecho (app nueva `incidents`):**
- `IncidenteReportado` (HU30 "reportar un incidente con máximo 3
  campos"): exactamente 3 campos que la persona llena — qué pasó,
  dónde, cuándo. Todo lo demás (quién, la organización, el estado) se
  completa solo. Pensado para que cualquier persona del personal
  clínico, sin entrenamiento técnico, pueda reportar algo sospechoso
  en segundos.

**Datos de ejemplo:** `seed_demo_data` ahora también siembra la
política de autonomía por defecto (las 7 reglas de la tabla oficial),
un registro de auditoría de ejemplo (el cierre de la vulnerabilidad de
la bomba de infusión) y un incidente reportado de ejemplo, para que
las pantallas nuevas no se vean vacías la primera vez.

**Tests:** 9 tests nuevos (`governance/tests.py`: políticas por
organización, crear/aprobar/rechazar solicitud + auditoría generada,
aislamiento multi-tenant de solicitudes, que el log rechace
PATCH/DELETE por API y por modelo; `incidents/tests.py`: reportar
incidente con los 3 campos, aislamiento multi-tenant). **Total ahora:
32 tests, todos verdes.**

**Lo que esta ronda deliberadamente NO hace (para no fabricar nada que
necesite una decisión de Bruno o de su asesor):**
- No implementa el motor de reglas contextuales R1-R5 (vulnerabilities)
  ni el cálculo de prioridad que describen — es lógica de negocio que
  conviene validar con Bruno antes de codificarla mal.
- No amplía el catálogo de controles ISO de 8 a los 93 reales de
  Anexo A, ni la tabla de mapeo hallazgo→control de la sección 8.5 —
  es trabajo mecánico pero largo (93 registros), mejor como una tarea
  aparte explícitamente pedida.
- No implementa MFA (HU29/RNF-04) — requiere elegir una librería TOTP
  y decidir el flujo de UX (¿QR? ¿app autenticadora?), screens nuevas
  en el frontend.
- No conecta el frontend a ninguna de estas 3 piezas nuevas (no hay
  pantallas de React para políticas de autonomía, solicitudes de
  aprobación, auditoría ni incidentes todavía) — todo esto vive por
  ahora solo en la API y en el admin de Django
  (`/admin/governance/` y `/admin/incidents/`).
- No toca SVM/spaCy, LangChain/máquina de estados del agente, ni
  conexión real a Wazuh/OpenVAS/Qwen — siguen siendo los puntos
  bloqueados por decisiones y recursos reales, no por falta de tiempo
  de esta ronda.

## Ronda 4 — 2026-10-20, noche (decisiones de Bruno sobre la lista de pendientes)

Bruno decidió: (1) empezar PostgreSQL, (2) catálogo ISO solo con lo más
relevante para salud, (3) implementar R1-R5, (4) MFA ahora no, (5) rol
Auditor que ve todo pero no hace nada, (6) pantallas nuevas sí,
(7) AWS después de terminar bien en la PC.

**Hecho:**
- **Rol Auditor de solo lectura real** (`common/permissions.py`, permiso
  por defecto de DRF): puede leer todo, cualquier escritura da 403. En
  la consola ve un aviso amarillo y los botones de acción deshabilitados.
  Usuario nuevo: `auditor_demo` / `demo12345`.
- **Permisos de Gerencia**: aprobar/rechazar solicitudes y cambiar
  niveles de autonomía solo lo puede hacer el Administrador. Una
  solicitud ya decidida no se puede volver a decidir.
- **Reglas R1-R5** (`vulnerabilities/priority.py`, módulo puro con 12
  pruebas unitarias). Campos nuevos: `Asset.exposure` (Internet /
  perimetral / interna) y `Vulnerability.actively_exploited` (KEV). La
  prioridad contextual se recalcula sola al guardar un hallazgo o al
  cambiar el activo, y guarda qué reglas aplicaron y por qué (la consola
  lo muestra en "Detalle > Por qué esta prioridad").
  Interpretación tomada en R1 ("mantiene o sube"): sube un nivel. Queda
  marcada para validar con el asesor (decisión D5 del documento).
- **Catálogo ISO 27001:2022 para salud** (`controls/catalogo_iso.py`):
  31 controles = todos los de la tabla de mapeo de la sección 8.5 + 6
  que ISO 27799 destaca para salud (backups, segregación de red
  biomédica, continuidad, concienciación, nube, plan de incidentes).
  Cada control tiene código, tema del Anexo A y "por qué importa en
  salud". Campo `Vulnerability.category`: al asignarlo, el hallazgo se
  vincula solo a los controles de la tabla (HU11). Endpoint
  `/api/controls/por-tema/` con % de cumplimiento por tema (HU13).
  Comando `python manage.py cargar_catalogo_iso`.
- **Pantallas nuevas**: Aprobaciones y autonomía, Registro de auditoría,
  Reportar incidente. Controles muestra código ISO, tema, motivo en
  salud y tarjetas por tema. Vulnerabilidades muestra prioridad
  contextual, etiqueta KEV y controles ISO vinculados.
- **El registro de auditoría ahora se llena con acciones reales**: crear
  y avanzar planes, verificaciones, análisis con IA, solicitudes,
  decisiones, cambios de política e incidentes.
- **PostgreSQL + Row-Level Security** (`common/rls.py`): probado en un
  PostgreSQL 16 real. Las políticas se aplican solas en cada `migrate`;
  la API corre cada petición con el rol restringido `centinela_app`; el
  registro de auditoría no tiene UPDATE/DELETE ni a nivel de motor.
  `python manage.py verificar_rls` lo demuestra (útil para la
  sustentación). Script de instalación: `docs/postgres_setup.sql`.

**Bug real encontrado gracias a RLS (y corregido también para SQLite):**
un usuario de la clínica A podía crear un plan, una solicitud de
aprobación o un hallazgo apuntando a registros de la clínica B, porque
los campos relacionados de DRF aceptaban cualquier id existente. Con RLS
PostgreSQL lo bloqueaba, pero en SQLite pasaba. Ahora
`common/serializers.py` limita esos campos a la organización del
usuario. 3 tests nuevos lo cubren.

**Tests:** 63 en SQLite (5 de RLS se saltan porque requieren Postgres) y
63/63 en PostgreSQL 16 con RLS. Build y lint del frontend sin errores.
Prueba de punta a punta en navegador sobre PostgreSQL: crear plan,
reportar incidente, aprobar como Gerencia, auditor en solo lectura.

**Sigue pendiente (a propósito):** MFA (Bruno: "ahora no"), despliegue en
AWS (después), validar R1-R5 y el catálogo con el asesor, SVM/spaCy,
LangChain, conexión real a Wazuh/OpenVAS/Qwen.

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

Entrar con `demo` (analista), `admin_demo` (administrador/Gerencia),
`coordinador_demo` (responsable de TI) o `auditor_demo` (auditor, solo
lectura). Clave para todos: `demo12345`.
