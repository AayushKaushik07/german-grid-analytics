-- Runs automatically on first container start (docker-entrypoint-initdb.d).
-- The ingestion job creates the tables themselves via pandas.to_sql; this file
-- only guarantees the schemas and indexes exist.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA raw IS
    'Landing zone. Written only by the ingestion job, read only by dbt staging.';
