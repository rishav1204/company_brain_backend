# API Contracts v1

Base path: `/api/v1`

## Auth and Context
- `GET /me`
- `GET /permissions/evaluate`
- `POST /auth/password/login` (dev compatibility)
- `POST /auth/dev/create-user` (dev helper)
- JWT bearer auth supported (`Authorization: Bearer <token>`)
- claim mapping:
  - tenant: `org_id`
  - user: `sub`
  - roles: `roles`
- bearer-only mode is default (`auth_mode=bearer_only`)
- JWT verification requires issuer/audience/expiry checks
- optional JWKS validation path supported for OIDC
- dev password route can mint short-lived JWT for local unblock
- dev create-user route provisions org/roles/password for local testing

## Sources and Ingestion
- `POST /sources`
- `GET /sources`
- `POST /sources/{sourceId}/sync`
- `GET /ingestion-runs`
- `POST /ingestion/runs/start`
- `POST /ingestion/runs/complete`
- `POST /identity/resolve`

## Knowledge and Retrieval
- `POST /query/context`
- `POST /query/explain`
- `GET /documents/{id}/citations`
- explain responses are LLM-generated when provider is configured

## Workflows and Tasks
- `GET /workflows`
- `POST /workflows/{id}/actions`
- `GET /workflows/{id}/timeline`

## Decisions and Memory
- `POST /decisions`
- `GET /decisions`
- `GET /memory`
- `POST /memory`

## Agent Runtime
- `POST /agents/run`
- `GET /agents/runs/{runId}`
- `POST /agents/runs/{runId}/approve`
- agent planning uses configured LLM provider (OpenAI by default)

## Audit, Compliance, and Governance (Module 4)
- `GET /audit/logs` (filters: event_type, entity_type, entity_id, trace_id)
- `GET /audit/timeline/{entity_type}/{entity_id}`
- `GET /audit/export`
- `GET /audit/evidence/{entity_type}/{entity_id}`
- `POST /audit/evidence/link`
- `POST /audit/ai-traces`
- `GET /audit/ai-traces/{trace_id}`
- `GET /compliance/events`
- `POST /compliance/gst/filed`
- `POST /compliance/gst/itc-mismatch`
- `POST /compliance/gst/delayed-filing`
- `POST /compliance/tds/{tds_type}`
- `GET /governance/violations`
- `POST /governance/violations/{id}/resolve`
- `POST /governance/evaluate`
- `POST /governance/risk/payment`
- `GET /governance/forensics/timeline`
- `GET /governance/forensics/rollback/{entity_type}/{entity_id}`
- `GET /governance/metrics`
- `GET /policies`
- `POST /policies`
- `POST /policies/simulate`
- Auditor read access required for audit/compliance read APIs

## Company-scoped APIs
- `GET /companies/{company_id}/invoices/{invoice_id}`
- `POST /companies/{company_id}/invoices`
- `POST /companies/{company_id}/workflows/{workflow_id}/actions`
- `GET /companies/{company_id}/reports/close-status`

## Observability
- `GET /metrics`
- `GET /events/recent`

## Queue and Reliability
- `POST /queue/enqueue`
- `POST /queue/process-next`
- backend runtime uses Redis queues + processed-idempotency set + DLQ queue

## Notifications (Module 5)
- `GET /notifications` — list (filters: `unread_only`, `notification_type`, `channel`, `priority`)
- `GET /notifications/unread-count`
- `POST /notifications/{id}/acknowledge`
- `POST /notifications/{id}/snooze` — body: `{ "until": "<ISO8601>" }`
- `GET /preferences` / `POST /preferences` — channel prefs + `quiet_hours`
- `GET /templates` / `POST /templates` / `PUT /templates/{id}`
- `POST /realtime/subscribe` — body: `{ "channel_key": "approval_queue" }`
- `GET /realtime/action-center` — poll toasts (optional `channel`)
- `GET /realtime/action-center/sse` — SSE stream
- `POST /webhooks/notifications/resend` / `whatsapp` — provider callbacks

## Memory Lifecycle
- `POST /memory/decay/run`

Response requirements:
- include `request_id` on every response
- include `citations[]` when AI-generated content exists
- include `confidence` and `verification_status`
- enforce HTTP `429` when rate limits are exceeded
- queue backend errors must return HTTP `503`
