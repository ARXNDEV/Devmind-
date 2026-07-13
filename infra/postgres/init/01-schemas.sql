-- Runs once on first container start (docker-entrypoint-initdb.d).
-- Two schemas, two service roles, per ADR-0003: `api` never touches
-- `codeintel` objects and vice versa. Cross-service access goes through
-- the HTTP contract, and the grants make violations fail at the DB.

CREATE SCHEMA IF NOT EXISTS product;
CREATE SCHEMA IF NOT EXISTS codeintel;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
  -- Runtime roles: DML only, no DDL. Migrations never run as these.
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'api_service') THEN
    CREATE ROLE api_service LOGIN PASSWORD 'api_dev_password';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'codeintel_service') THEN
    CREATE ROLE codeintel_service LOGIN PASSWORD 'codeintel_dev_password';
  END IF;
  -- Release-step role: owns DDL (drizzle migrator needs schema-create for
  -- its bookkeeping). Only migration jobs use this credential.
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'migrator') THEN
    CREATE ROLE migrator LOGIN PASSWORD 'migrator_dev_password' CREATEROLE;
  END IF;
END
$$;

GRANT CREATE ON DATABASE devmind TO migrator;
GRANT USAGE, CREATE ON SCHEMA product TO migrator;
GRANT USAGE ON SCHEMA product TO api_service;
GRANT USAGE, CREATE ON SCHEMA codeintel TO codeintel_service;

ALTER ROLE api_service SET search_path = product;
ALTER ROLE codeintel_service SET search_path = codeintel;

-- Tables created by migrator become readable/writable by the runtime role.
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA product
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO api_service;
ALTER DEFAULT PRIVILEGES FOR ROLE migrator IN SCHEMA product
  GRANT USAGE, SELECT ON SEQUENCES TO api_service;
-- codeintel manages its own schema objects at runtime (single role) for now.
ALTER DEFAULT PRIVILEGES IN SCHEMA codeintel
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO codeintel_service;
