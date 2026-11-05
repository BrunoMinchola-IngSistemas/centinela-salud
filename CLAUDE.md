# Centinela Salud — contexto para Claude Code

Tesis de Bruno Minchola y Andre Zapata: agente de IA para gestionar
vulnerabilidades de ciberseguridad en PyMEs de salud, basado en ISO/IEC
27001:2022. Caso de estudio: clínica "SaludMedica" (en la demo: "Clínica
San Lucas (demo)"). Responde y escribe código/comentarios en español.

Bruno prefiere respuestas cortas, paso a paso, con el resultado primero.
**Antes de crear o mover archivos fuera del código, dale un resumen corto
de lo que vas a hacer.**

## Estructura

- `backend/` Django 6 + DRF. Apps: `accounts` (organización, perfil, rol),
  `assets`, `vulnerabilities` (+ `priority.py` reglas R1-R5), `controls`
  (+ `catalogo_iso.py`, 34 controles ISO para salud, Ley 29733 y mapeo hallazgo→control),
  `remediation`, `evidence`, `governance` (autonomía, aprobaciones,
  auditoría solo-inserción), `incidents` (reporte en 3 campos),
  `integrations` (Wazuh/OpenVAS/Kaspersky en modo demo, asistente, Qwen/Bedrock),
  `notificaciones` (avisos por persona), `informes` (Risk Score, reportes,
  cuadro ejecutivo), `common` (permisos por rol y módulo `modulos.py`,
  Row-Level Security, seudonimización, `programador` de tareas).
- `deploy/` Docker, Caddy, docker-compose, scripts de AWS y `validar_hu.py`.
- `frontend/` React + Vite. Páginas en `src/pages/`, API en `src/api/resources.js`.
- `docs/` script de PostgreSQL y comparación de hosting.
- `NOTES.md` historial de rondas de trabajo; `GUIA_RAPIDA.md` guía corta.

## Comandos (Windows, PowerShell)

```powershell
# Backend
cd backend
venv\Scripts\activate
python manage.py migrate
python manage.py seed_demo_data --reset   # datos demo
python manage.py runserver
python manage.py test                     # pruebas
python manage.py verificar_rls            # solo con PostgreSQL

# Frontend
cd frontend
npm run dev      # http://localhost:5173
npm run build
npm run lint
```

Usuarios demo (clave `demo12345`): `demo` (analista), `admin_demo`
(administrador/Gerencia), `coordinador_demo` (responsable de TI),
`cumplimiento_demo` (oficial de cumplimiento), `personal_demo` (personal
administrativo), `auditor_demo` (auditor, solo lectura).

Validar HU de punta a punta: `python deploy/validar_hu.py --url http://localhost:8000 --clave demo12345`
Tareas periódicas: `python manage.py programador --una-vez`

## Reglas del proyecto

- Multi-organización: toda vista filtra por la organización del usuario
  (`common/mixins.py`) y los campos relacionados editables usan
  `OrganizationScopedRelationsMixin` (`common/serializers.py`). No romper esto.
- Toda vista nueva declara `modulo = "..."` (ver `common/modulos.py`, HU28).
- Permisos: el rol Auditor no puede escribir (`common/permissions.py`);
  aprobar/rechazar y cambiar políticas de autonomía es solo del Administrador.
- Acciones relevantes se registran con `governance.audit.registrar(...)`.
  El registro de auditoría nunca se edita ni se borra.
- Base de datos: SQLite si `POSTGRES_DB` está vacío en `backend/.env`;
  PostgreSQL si tiene valor. En PostgreSQL, RLS se aplica solo en cada
  `migrate` (`common/rls.py`). Si agregas un modelo con `organization`,
  añádelo a `TABLAS_CON_ORGANIZACION` en `common/rls.py`.
- Después de cambiar modelos: `makemigrations`, `migrate`, `test`.
- Antes de un commit: `python manage.py test` y `npm run build` sin errores.
- Nunca subas `backend/.env`, `db.sqlite3`, `venv/` ni `node_modules/`.
- Mensajes de commit en español, explicando el porqué.

## Pendiente conocido

Desplegar en AWS (`docs/Pasos_AWS.txt`), validar con el asesor R1-R5,
catálogo, Ley 29733 y Risk Score; spaCy/LangChain; conexión real a
Wazuh/OpenVAS/Qwen. Ver `NOTES.md` (Ronda 5).
