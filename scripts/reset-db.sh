#!/usr/bin/env bash
# Reset the local development database.
# Drops and recreates the `thrn` database, then applies all migrations in order.
# Safe to run repeatedly. Requires docker-compose to be running.

set -euo pipefail

# Load .env if present so POSTGRES_* vars are available.
if [[ -f "$(dirname "$0")/../.env" ]]; then
  # shellcheck disable=SC1091
  set -a; source "$(dirname "$0")/../.env"; set +a
fi

PG_USER="${POSTGRES_USER:-thrn}"
PG_DB="${POSTGRES_DB:-thrn}"
CONTAINER="${POSTGRES_CONTAINER:-thrn-postgres}"

echo "→ Dropping and recreating database ${PG_DB} in container ${CONTAINER}"
docker exec -i "${CONTAINER}" psql -U "${PG_USER}" -d postgres -v ON_ERROR_STOP=1 <<SQL
DROP DATABASE IF EXISTS ${PG_DB};
CREATE DATABASE ${PG_DB};
SQL

MIGRATIONS_DIR="$(cd "$(dirname "$0")/.." && pwd)/infra/postgres/migrations"
echo "→ Applying migrations from ${MIGRATIONS_DIR}"
for f in "${MIGRATIONS_DIR}"/*.sql; do
  echo "  • $(basename "$f")"
  docker exec -i "${CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 < "$f" >/dev/null
done

echo "✓ Database ${PG_DB} reset and migrated."
