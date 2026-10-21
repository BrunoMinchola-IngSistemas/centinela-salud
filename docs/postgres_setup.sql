-- ============================================================
-- Centinela Salud · preparación de PostgreSQL (se corre UNA vez)
-- ============================================================
-- Córrelo como el superusuario "postgres" (pgAdmin > Query Tool sobre la
-- base "postgres", o en la terminal:  psql -U postgres -f postgres_setup.sql)
--
-- ANTES de correrlo, cambia la clave de la línea marcada con <<< por una
-- tuya, y pon esa MISMA clave en backend\.env (POSTGRES_PASSWORD).
-- ============================================================

-- 1) Usuario con el que se conecta Django. Es dueño de las tablas y
--    corre las migraciones. CREATEDB solo hace falta para que
--    "python manage.py test" pueda crear su base temporal de pruebas.
CREATE ROLE centinela LOGIN PASSWORD 'cambia-esta-clave' CREATEDB;   -- <<< cambia la clave

-- 2) Rol restringido SIN login. La API se "pone" este rol en cada
--    petición (SET ROLE) y ahí PostgreSQL aplica Row-Level Security.
CREATE ROLE centinela_app NOLOGIN;
GRANT centinela_app TO centinela;

-- 3) La base de datos, propiedad de "centinela".
CREATE DATABASE centinela OWNER centinela ENCODING 'UTF8';

-- Listo. Las tablas, permisos y políticas RLS las crea Django solo con:
--   python manage.py migrate
