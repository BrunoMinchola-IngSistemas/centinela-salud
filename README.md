# Centinela Salud

Consola de ciberseguridad asistida por IA para PyMEs del sector salud:
centraliza vulnerabilidades (Wazuh + OpenVAS), las relaciona con
controles (ISO 27001, HIPAA, CIS), genera recomendaciones con Qwen
(corriendo localmente en la sede del cliente), administra planes de
corrección y conserva evidencias con huella SHA-256.

## Estructura

```
centinela-salud/
├── backend/        Django 6 + Django REST Framework
│   ├── accounts/        Organización (tenant), usuarios, roles
│   ├── assets/           Servidores, estaciones, dispositivos médicos, apps
│   ├── vulnerabilities/  Hallazgos normalizados + fuentes (Wazuh/OpenVAS/Kaspersky)
│   ├── controls/         Controles de seguridad mapeados a marcos normativos
│   ├── remediation/      Planes de corrección (kanban) + verificación/reescaneo
│   ├── evidence/         Evidencias inmutables con huella SHA-256
│   ├── integrations/     Clientes de Wazuh, OpenVAS, Qwen y Kaspersky (opcional)
│   └── common/           Aislamiento multi-tenant por organización
└── frontend/        React + Vite
    ├── src/api/          Cliente axios + funciones por recurso
    ├── src/context/      Autenticación por token
    ├── src/layout/       Marco de la consola (barra superior, navegación)
    └── src/pages/        Panel general, vulnerabilidades, plan, verificación, etc.
```

## Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # completa las variables, o déjalas para usar SQLite local
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sin `POSTGRES_DB` en el `.env`, usa SQLite automáticamente (útil para
desarrollar sin levantar RDS). La API queda en `http://localhost:8000/api/`.

### Autenticación

Usa `rest_framework.authtoken`. Para obtener un token:

```bash
curl -X POST http://localhost:8000/api/auth/login/ -d "username=demo&password=demo12345"
```

Cada usuario necesita un perfil (`accounts.User`) ligado a una
`Organization`; sin eso, la API rechaza las peticiones porque todos
los datos están aislados por organización (ver `common/mixins.py`).

### Datos de prueba

```bash
python manage.py seed_demo_data        # crea datos de demo si no existen
python manage.py seed_demo_data --reset  # los borra y recrea desde cero
```

Crea el usuario `demo` / `demo12345`, 8 activos, 2 fuentes, 8 controles
y 6 vulnerabilidades en distintos estados (abierta, en plan, en
verificación, cerrada), para poder ver la consola con datos realistas
sin crear todo a mano.

### Pasar de SQLite a PostgreSQL (con Row-Level Security)

El backend usa SQLite por defecto para que no haga falta instalar nada.
PostgreSQL es la base elegida en el Benchmarking de la tesis (sección
3.4) sobre todo por **Row-Level Security (RLS)**: el propio motor se
niega a mostrar filas de otra clínica, aunque el código se olvide de
filtrar. Está implementado en `backend/common/rls.py` y se activa solo.

1. Instala PostgreSQL 16 o 17 (en Windows: instalador de
   postgresql.org, deja el puerto 5432 y anota la clave de `postgres`).
2. Abre `docs/postgres_setup.sql`, cambia `cambia-esta-clave` por una
   clave tuya y córrelo como `postgres` (pgAdmin > Query Tool, o
   `psql -U postgres -f docs/postgres_setup.sql`). Crea el usuario
   `centinela`, el rol restringido `centinela_app` y la base.
3. En `backend/.env`:
   ```
   POSTGRES_DB=centinela
   POSTGRES_USER=centinela
   POSTGRES_PASSWORD=la-clave-del-paso-2
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   ```
   Con `POSTGRES_DB` lleno, Django usa PostgreSQL automáticamente.
4. Migra (esto también crea las políticas RLS), siembra y comprueba:
   ```bash
   python manage.py migrate
   python manage.py seed_demo_data
   python manage.py verificar_rls
   ```
   `verificar_rls` debe terminar en "RLS activo y funcionando.".
5. Para volver a SQLite basta con dejar `POSTGRES_DB=` vacío.

Cómo funciona RLS aquí: Django se conecta como `centinela` (dueño de
las tablas: migraciones y comandos). En cada petición a la API, tras
autenticar al usuario, la conexión hace `SET ROLE centinela_app` y
guarda su organización en `app.current_org`; las políticas solo dejan
ver y escribir filas de esa organización. El registro de auditoría no
tiene permisos de UPDATE/DELETE para `centinela_app`.

### Integraciones

`integrations/` trae los clientes de Wazuh (API REST), OpenVAS (GMP,
pendiente de conectar `python-gvm`), Qwen (API estilo Ollama) y un
stub opcional de Kaspersky. Todas las credenciales se leen de
variables de entorno (ver `.env.example`); ninguna va en el código.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env   # déjalo vacío en desarrollo, usa el proxy de Vite
npm run dev
```

Queda en `http://localhost:5173`. En desarrollo, las llamadas a
`/api/...` se redirigen automáticamente al backend en el puerto 8000
(ver `vite.config.js`). En producción, define `VITE_API_URL` apuntando
a la API real.

## Próximos pasos sugeridos

1. Conectar `integrations/openvas.py` con `python-gvm` contra el GVM real.
2. Conectar `integrations/wazuh.py` con credenciales reales del manager.
3. Desplegar Qwen (Ollama/vLLM) en la sede de la PyME y apuntar `QWEN_API_URL`.
4. Pasar de SQLite a RDS PostgreSQL en el entorno de AWS.
5. Agregar tareas programadas (Celery beat o EventBridge) para sincronizar automáticamente.
