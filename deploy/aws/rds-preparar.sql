-- =====================================================================
-- Preparación de Amazon RDS PostgreSQL para Centinela Salud (UNA vez).
-- Se corre desde la EC2 (la base es privada), con el usuario MAESTRO
-- de RDS (p. ej. "postgres_admin"):
--
--   psql "host=<endpoint-rds> port=5432 dbname=postgres user=postgres_admin sslmode=verify-full sslrootcert=/opt/centinela/global-bundle.pem" \
--        -v clave_app="'<CLAVE-DEL-USUARIO-centinela>'" -v maestro=postgres_admin -f rds-preparar.sql
--
-- Diferencias con docs/postgres_setup.sql (PC): sin CREATEDB (en la nube
-- no se corren pruebas) y el maestro se hace miembro de "centinela" para
-- poder crear la base a su nombre (requisito de PostgreSQL 15+ en RDS).
-- =====================================================================

CREATE ROLE centinela LOGIN PASSWORD :clave_app;
CREATE ROLE centinela_app NOLOGIN;            -- rol restringido: RLS (cada clínica ve lo suyo)
GRANT centinela_app TO centinela;             -- la API hace SET ROLE centinela_app en cada petición
GRANT centinela TO :maestro;

CREATE DATABASE centinela OWNER centinela ENCODING 'UTF8';

\c centinela
-- Nadie más que el dueño crea objetos en el esquema público.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE centinela FROM PUBLIC;
GRANT CONNECT ON DATABASE centinela TO centinela;

-- Las tablas, permisos y políticas RLS las crea Django con:
--   docker compose run --rm api python manage.py migrate
