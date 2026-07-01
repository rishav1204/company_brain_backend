#!/usr/bin/env bash
# Run database migrations against Neon (one-off before first prod deploy).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/company-brain}"
ENV_FILE="${APP_DIR}/.env"
MIGRATIONS_DIR="${APP_DIR}/backend/migrations"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${POSTGRES_DSN:-}" ]]; then
  echo "ERROR: POSTGRES_DSN not set. Run bootstrap.sh first or export POSTGRES_DSN."
  exit 1
fi

echo "==> Running migrations from ${MIGRATIONS_DIR}"
cd "${APP_DIR}"
python backend/scripts/run_migrations.py \
  --dsn "${POSTGRES_DSN}" \
  --migrations-dir "${MIGRATIONS_DIR}"

echo "==> Migrations complete"
