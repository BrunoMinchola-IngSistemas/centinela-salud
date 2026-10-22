-- ============================================================
-- Centinela Salud · preparación de PostgreSQL (se corre UNA sola vez)
-- ============================================================
-- En pgAdmin 4:
--   1. Servers > PostgreSQL (16 o 17) > Databases > postgres
--      clic derecho > Query Tool.
--   2. Abre este archivo (ícono de carpeta) o pega su contenido.
--   3. Cambia 'cambia-esta-clave' por una clave tuya (línea marcada <<<).
--      Esa MISMA clave va en backend\.env  ->  POSTGRES_PASSWORD=
--   4. IMPORTANTE: córrelo en DOS partes (PostgreSQL no permite crear
--      una base de datos en el mismo bloque que otras órdenes):
--        PARTE 1: selecciona con el mouse solo las líneas de la PARTE 1
--                 y presiona F5.  Debe decir "Query returned successfully".
--        PARTE 2: selecciona solo la línea CREATE DATABASE y presiona F5.
--
-- (Desde la terminal también funciona de una sola vez:
--    psql -U postgres -f postgres_setup.sql )
-- ============================================================


-- ---------------- PARTE 1 (seleccionar estas 3 líneas + F5) ----------------
CREATE ROLE centinela LOGIN PASSWORD 'cambia-esta-clave' CREATEDB;   -- <<< cambia la clave
CREATE ROLE centinela_app NOLOGIN;
GRANT centinela_app TO centinela;


-- ---------------- PARTE 2 (seleccionar esta línea + F5) ----------------
CREATE DATABASE centinela OWNER centinela ENCODING 'UTF8';


-- Qué hace cada cosa:
--   centinela      -> usuario con el que se conecta Django. Dueño de las
--                     tablas; corre las migraciones. CREATEDB es solo para
--                     que "python manage.py test" cree su base de pruebas.
--   centinela_app  -> rol restringido SIN login. La API se "pone" este rol
--                     en cada petición y ahí PostgreSQL aplica Row-Level
--                     Security (cada clínica solo ve lo suyo).
--   centinela (BD) -> la base de datos.
-- Las tablas, permisos y políticas RLS las crea Django solo con:
--   python manage.py migrate
