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
  (+ `catalogo_iso.py`, 31 controles ISO para salud y mapeo hallazgo→control),
  `remediation`, `evidence`, `governance` (autonomía, aprobaciones,
  auditoría solo-inserción), `incidents` (reporte en 3 campos),
  `integrations` (Wazuh/OpenVAS/Qwen, aún con datos de ejemplo),
  `common` (permisos por rol, Row-Level Security, mixins).
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
`auditor_demo` (auditor, solo lectura).

## Reglas del proyecto

- Multi-organización: toda vista filtra por la organización del usuario
  (`common/mixins.py`) y los campos relacionados editables usan
  `OrganizationScopedRelationsMixin` (`common/serializers.py`). No romper esto.
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

MFA (HU29), despliegue en AWS, validar R1-R5 y el catálogo con el asesor,
SVM/spaCy, LangChain, conexión real a Wazuh/OpenVAS/Qwen. Ver `NOTES.md`.
