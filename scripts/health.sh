#!/usr/bin/env bash
# Quick health check for local dev services.
set -euo pipefail

if [[ -f "$(dirname "$0")/../.env" ]]; then
  # shellcheck disable=SC1091
  set -a; source "$(dirname "$0")/../.env"; set +a
fi

PG_CONTAINER="${POSTGRES_CONTAINER:-thrn-postgres}"
TS_HOST="${TYPESENSE_HOST:-localhost}"
TS_PORT="${TYPESENSE_PORT:-8108}"
PG_USER="${POSTGRES_USER:-thrn}"
PG_DB="${POSTGRES_DB:-thrn}"

echo "→ PostgreSQL"
if docker exec "${PG_CONTAINER}" pg_isready -U "${PG_USER}" -d "${PG_DB}" >/dev/null 2>&1; then
  echo "  ✓ ${PG_CONTAINER} is accepting connections"
else
  echo "  ✗ ${PG_CONTAINER} not ready"; exit 1
fi

echo "→ Typesense"
if curl -sf "http://${TS_HOST}:${TS_PORT}/health" >/dev/null; then
  echo "  ✓ Typesense healthy at http://${TS_HOST}:${TS_PORT}"
else
  echo "  ✗ Typesense not responding"; exit 1
fi

echo "✓ All services healthy."
