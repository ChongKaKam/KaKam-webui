#!/bin/sh
set -eu
# Official postgres entrypoint sources this script only for an EMPTY data volume.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 --set memory_password="$MEMORY_DB_PASSWORD" <<'SQL'
CREATE ROLE kakam_memory LOGIN PASSWORD :'memory_password';
CREATE DATABASE kakam_memory OWNER kakam_memory;
\connect kakam_memory
CREATE EXTENSION vector;
REVOKE ALL ON DATABASE kakam_memory FROM PUBLIC;
GRANT CONNECT ON DATABASE kakam_memory TO kakam_memory;
SQL
