# Helm Charts

Use this directory for Kubernetes deployment manifests/Helm charts.

Recommended chart split:
- `finance-api`
- `agent-runner`
- `worker-ingestion`
- `worker-retrieval`
- `worker-notifications`

Monitoring artifacts added:
- `alerts-rules.yaml` for Prometheus alerting rules
- `grafana-dashboard.json` as baseline dashboard definition
- includes queue lag and OTEL readiness monitoring panels/alerts

Deployment artifacts:
- `finance-api-values.yaml` for API deployment values
- `worker-values.yaml` for worker deployment values
- `scheduler-values.yaml` for scheduler deployment values
