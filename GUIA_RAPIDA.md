# Guía rápida — Centinela Salud

Resumen corto de dónde está todo y qué sigue. Si quieres el detalle
técnico completo, está en `README.md` y `NOTES.md`.

## 1. Estado actual (20 oct 2026)

✅ Backend (Django) y frontend (React) funcionando juntos en tu compu.
✅ 3 cuentas de prueba con roles distintos: `demo` (analista),
   `admin_demo` (admin), `coordinador_demo` (TI) — clave `demo12345`.
✅ 16 pruebas automáticas, todas verdes.
✅ Manejo de errores real en las 8 pantallas (ya no se ve "vacío"
   cuando en realidad algo falló).
✅ Todo en GitHub: https://github.com/BrunoMinchola-IngSistemas/centinela-salud
✅ Todo copiado en `D:\Tesis_Obj3`.

❌ Todavía usa SQLite (una base de datos en un archivo), no
   PostgreSQL. Ver sección 3.
❌ Todavía no está en internet — solo corre en tu compu. Ver sección 4.
❌ Wazuh y OpenVAS reales no están conectados (solo hay datos de
   ejemplo). Eso es trabajo para más adelante, no urgente ahora.

## 2. Cómo seguir trabajando con terminal real (Claude Code)

En este chat (la nube), **no puedo escribir en tu Terminal** — solo
puedo hacer clic, por una restricción de la plataforma. Por eso cada
vez que necesitabas correr un comando, te lo tuve que dictar para que
tú lo escribieras.

Para que yo (Claude) pueda usar la Terminal de tu compu directamente
— instalar paquetes, correr pruebas, hacer commits — sin que tengas
que teclear nada, usa **Claude Code** instalado en tu máquina:

1. Abre una Terminal en `D:\Tesis_Obj3` (clic derecho → "Abrir en
   Terminal", o `cd D:\Tesis_Obj3` en PowerShell).
2. Instala Claude Code (una sola vez):
   ```
   npm install -g @anthropic-ai/claude-code
   ```
   (Necesitas Node.js instalado; si no lo tienes, bájalo de
   nodejs.org primero.)
3. Corre:
   ```
   claude
   ```
4. Te va a pedir iniciar sesión con tu cuenta de Claude (la misma que
   usas aquí). Una vez dentro, ya estás en la misma carpeta del
   proyecto (`D:\Tesis_Obj3`), con Terminal real.
5. Dile lo que necesites, igual que aquí — pero ahí sí puedo escribir
   comandos, correr el servidor, instalar cosas, etc. sin pedirte que
   los tipees tú.

Ese repo de GitHub es el punto de encuentro entre esta conversación
(la nube) y Claude Code (tu compu): lo que yo suba aquí, lo puedes
bajar ahí con `git pull`, y viceversa.

## 3. Qué falta para la Base de Datos

Hoy usas SQLite (un archivo, no un servidor de verdad). Para producción
necesitas PostgreSQL. Ya dejé la guía paso a paso en el `README.md`
("Pasar de SQLite a PostgreSQL"). En resumen, necesitas decidir:

- **¿Local o en la nube?** Para seguir probando en tu compu, puedes
  instalar PostgreSQL local (gratis). Para producción, va en la nube
  (ver sección 4 — normalmente es el mismo proveedor que hostea el
  backend).
- **Nombre de base, usuario, clave** — los eliges tú, van en el
  archivo `.env`, nunca en el código.
- El resto es automático: con esas 5 variables completas, Django usa
  PostgreSQL solo.

**No es urgente hacerlo ya.** SQLite funciona bien para seguir
desarrollando y para la sustentación de tesis si es una demo local.
Se vuelve necesario cuando quieras que varias personas usen el sistema
al mismo tiempo, o cuando lo subas a internet.

## 4. Desplegar en la nube (dato sensible de salud)

Como el sistema maneja datos de pacientes (HIPAA), esto no es "subir
el código a cualquier hosting gratis y ya". Temas a decidir, en orden:

1. **¿Demo con datos falsos o sistema real con pacientes reales?**
   Si es solo para mostrar en la tesis, un hosting gratuito o barato
   basta y no hay problema de sensibilidad (los datos son inventados).
   Si en algún momento va a manejar pacientes reales, se necesita un
   proveedor con garantías de cifrado, backups y control de acceso
   (normalmente ya no "gratis").
2. **Opciones económicas/gratuitas para la demo** (lo vemos en
   detalle en el próximo mensaje, como pediste): típicamente backend +
   base de datos en un mismo proveedor (Render, Railway, Fly.io) y el
   frontend en otro (Vercel, Netlify, Cloudflare Pages) — todos tienen
   capa gratuita que alcanza para una demo de tesis.
3. **AWS** (lo que ya contemplaba la arquitectura original) es la
   opción "seria" a largo plazo, pero no tiene capa gratiuta tan
   generosa y pide tarjeta desde el inicio.

### Comparación de dónde desplegar (para la demo de tesis)

La arquitectura real tiene 3 piezas que viven en lugares distintos:
**backend (Django)**, **base de datos (PostgreSQL)** y **frontend
(React ya compilado, son solo archivos estáticos)**. Wazuh/OpenVAS/Qwen
quedan fuera de esto — para una demo de tesis siguen siendo los datos
de ejemplo, no hace falta desplegarlos de verdad.

| Opción | Backend + BD | Frontend | Costo | Qué tan fácil |
|---|---|---|---|---|
| **Render** (recomendado para empezar) | Web Service (Django) + PostgreSQL, ambos gratis | Static Site, gratis | $0 (con límites: el backend gratis "duerme" tras 15 min sin uso y tarda ~30s en despertar) | Alta — conecta el repo de GitHub y detecta Django solo |
| **Railway** | Backend + PostgreSQL en el mismo proyecto | Puede ir ahí mismo o en Vercel | ~$5/mes de crédito gratis al mes, luego se cobra uso | Alta — similar a Render, un poco más rápido, menos generoso en el plan gratis |
| **Fly.io** | Backend en una VM pequeña + PostgreSQL (Fly Postgres) | Se puede servir junto con el backend | Capa gratis pequeña (requiere tarjeta para verificar, aunque no cobra si no te pasas) | Media — más control, un poco más de configuración |
| **Vercel / Netlify / Cloudflare Pages** | — (no corren Django) | Ideal para el frontend solo | Gratis para proyectos pequeños | Alta |
| **AWS** (la arquitectura "real" de tu tesis) | EC2/RDS o ECS + RDS PostgreSQL | S3 + CloudFront | Sin capa gratis real para esto (la free tier de 12 meses no alcanza cómodo para RDS + EC2 corriendo todo el tiempo) | Baja — pide tarjeta, más piezas que configurar, pero es lo que tu documento de arquitectura original ya contemplaba |

**Recomendación concreta para la sustentación de tesis:**
1. **Backend + PostgreSQL → Render** (o Railway). Gratis, y Render
   detecta un proyecto Django casi sin configurar nada: solo pide el
   comando de arranque (`gunicorn config.wsgi`) y las variables de
   `.env`.
2. **Frontend → Vercel o la misma Render como Static Site**, apuntando
   `VITE_API_URL` a la URL que te da Render para el backend.
3. Esto es **para la demo con datos inventados**, no para pacientes
   reales — no hay tema de HIPAA porque no hay datos reales de nadie.
   Si en algún momento se usa con pacientes de verdad, ahí sí hay que
   hablar de un proveedor con garantías (cifrado en reposo, BAA/acuerdo
   de confidencialidad, backups) — eso ya es otra conversación, para
   cuando el proyecto pase de tesis a producción real.

No armé los archivos de despliegue (Dockerfile, `render.yaml`, etc.)
todavía porque eso hay que probarlo contra una cuenta real de Render
para confirmar que funciona — prefiero no dejarte configuración sin
probar. Cuando elijas el proveedor, lo hacemos juntos (puede ser aquí
mismo o en Claude Code con tu Terminal) y lo probamos en vivo.
