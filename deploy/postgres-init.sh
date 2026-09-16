#!/bin/bash
# Creates the broker database next to the orthanc index on first start.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
    SELECT 'CREATE DATABASE mwl' WHERE NOT EXISTS (
        SELECT FROM pg_database WHERE datname = 'mwl'
    )\gexec
SQL
