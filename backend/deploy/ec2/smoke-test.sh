#!/usr/bin/env bash
# Smoke tests for deployed API (run from laptop or EC2).
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "==> GET ${BASE_URL}/health"
curl -sf "${BASE_URL}/health" | python -m json.tool

echo "==> GET ${BASE_URL}/ready"
READY_JSON="$(curl -sf "${BASE_URL}/ready")"
echo "${READY_JSON}" | python -m json.tool

if echo "${READY_JSON}" | grep -q '"postgres": "ok"'; then
  echo "Postgres: ok"
else
  echo "WARN: postgres not ok in /ready"
fi

if echo "${READY_JSON}" | grep -q '"redis": "ok"'; then
  echo "Redis: ok"
else
  echo "WARN: redis not ok in /ready"
fi

echo "==> Smoke checks passed (health + ready reachable)"
