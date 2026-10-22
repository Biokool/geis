-- =====================================================================
-- GEIS · db/init.sql — inicialización del contenedor PostGIS
-- ---------------------------------------------------------------------
-- Se monta en /docker-entrypoint-initdb.d/ y corre SOLO en la primera
-- creación del volumen pgdata.
-- Alcance EXCLUSIVO de este archivo: extensiones y esquemas base.
-- Las TABLAS las crea el worker backend vía Alembic (migraciones).
-- DDL idempotente (IF NOT EXISTS), según §5 del SRS.
-- =====================================================================

-- Extensión espacial obligatoria (§4.3 del SRS)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Búsqueda difusa de nombres (giros, colonias)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Generación de UUIDs (tokens de invitado, reportes)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Esquemas de datos: prod (datos curados), stg (staging), quarantine
CREATE SCHEMA IF NOT EXISTS prod;
CREATE SCHEMA IF NOT EXISTS stg;
CREATE SCHEMA IF NOT EXISTS quarantine;
