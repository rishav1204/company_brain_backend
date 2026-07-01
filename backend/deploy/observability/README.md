# Observability stack (OTEL Collector + Tempo + Prometheus + Grafana)

```bash
cd backend/deploy/observability
docker compose -f docker-compose.observability.yml up -d
```

Point the API at the collector:

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
OBSERVABILITY_REQUIRE_IN_PROD=true
```

Grafana: http://localhost:3001 (admin/admin)

Prometheus: http://localhost:9090

Tempo traces are received via the OTEL collector on ports 4317/4318.

Import `backend/charts/grafana-dashboard.json` from the Grafana UI or use the mounted volume in compose.
