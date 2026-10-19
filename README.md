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
