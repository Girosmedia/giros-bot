-- =============================================================================
-- Giros-bot — Setup inicial de PostgreSQL
-- Ejecutar como superusuario (postgres):
--   sudo -u postgres psql -f scripts/setup_postgres.sql
-- =============================================================================

-- 1. Crear usuario dedicado
--    Cambiar la contraseña antes de ejecutar en producción.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'giros_bot') THEN
        CREATE USER giros_bot WITH PASSWORD 'giros_bot_2026';
        RAISE NOTICE 'Usuario giros_bot creado.';
    ELSE
        RAISE NOTICE 'Usuario giros_bot ya existe, se omite creación.';
    END IF;
END
$$;

-- 2. Crear base de datos
SELECT 'CREATE DATABASE giros_bot OWNER giros_bot'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'giros_bot')\gexec

-- 3. Conectar a la BD y otorgar privilegios
\connect giros_bot

-- Ownership del schema public al usuario (necesario en PG 15+)
ALTER SCHEMA public OWNER TO giros_bot;
GRANT ALL ON SCHEMA public TO giros_bot;
GRANT ALL PRIVILEGES ON DATABASE giros_bot TO giros_bot;

-- Privilegios sobre tablas futuras
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO giros_bot;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON SEQUENCES TO giros_bot;

\echo '✓ Base de datos giros_bot y usuario giros_bot configurados correctamente.'
\echo '⚠  Recuerda cambiar la contraseña en producción.'
\echo '   String de conexión: postgresql+asyncpg://giros_bot:giros_bot_2026@localhost:5432/giros_bot'
