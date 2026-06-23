# Module 7 — Integration Platform + Connector Architecture

This module is the **provider/connectivity layer** for the Finance OS.

**Golden rule**
- **Domain modules** own business orchestration and rules (Workflows, Documents, Notifications, GST logic, Reconciliation logic).
- **Module 7** owns external connectivity and provider implementations (OCR providers, Slack/Teams, email providers, webhooks, connectors, sync jobs, ingestion).

---

## What’s implemented (current)

### DB (`integrations.*`)
Migration: `backend/migrations/027_integrations_platform.sql`

Tables (all org-isolated via RLS):
- `integrations.connectors`
- `integrations.webhook_subscriptions`
- `integrations.webhook_deliveries`
- `integrations.sync_jobs`
- `integrations.ingestion_records`
- `integrations.api_keys`

### Connector registry (runtime)
- Registry: `app/modules/platform/integrations/services/connector_registry.py`
- Endpoint: `GET /api/v1/integrations/registry`

### OCR providers moved behind Module 7 connectors
Documents module now resolves OCR via registry (no longer directly calling provider SDKs).

Connectors:
- `ocr/aws_textract`
- `ocr/gcp_documentai`

### Webhooks (outbound + inbound)
- Outbound subscriptions: stored in `integrations.webhook_subscriptions`
- Deliveries tracked in `integrations.webhook_deliveries`
- Event publishing dispatches webhooks automatically via `PlatformEventService.publish(...)`
- Delivery capabilities (Module 7):
  - exponential backoff retries
  - terminal failure (`failed`) after max attempts
  - delivery history endpoints
  - replay endpoint for a specific delivery id

Inbound webhook receiver:
- `POST /api/v1/integrations/webhooks/inbound/{org_id}/{subscription_id}`
- Requires `X-Webhook-Signature` (HMAC-SHA256 over raw request body)
- Creates `integrations.ingestion_records` and emits `webhook.received`

### API Keys
- Create/list/revoke API keys
- Keys are **hashed** at rest; raw key is returned **only once** at creation time

---

## Environment variables

- `INTEGRATIONS_CREDENTIALS_KEY` (required to encrypt connector credentials & webhook secrets)
- `INTEGRATIONS_API_KEY_RATE_LIMIT_PER_MINUTE` (per-minute limit for `cbk_` keys; Redis-backed if `REDIS_URL` set)

---

## API Reference

All routes are under: **`/api/v1/integrations`**

### Connectors

#### `POST /connectors`
Create a connector record (credentials are encrypted at rest and never returned).

Request:
```json
{
  "connector_type": "ocr",
  "provider_name": "aws_textract",
  "config": { "region": "ap-south-1" },
  "credentials": { "access_key_id": "…", "secret_access_key": "…" }
}
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "connector_type": "ocr", "provider_name": "aws_textract", "status": "active", "config": {} } }
```

#### `GET /connectors`
List connectors.

Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "connector_type": "ocr", "provider_name": "aws_textract" } ] }
```

### Registry

#### `GET /registry`
List registered runtime connectors and health.

Response:
```json
{
  "items": [
    { "connector_type": "ocr", "provider_name": "aws_textract", "health": { "ready": true } }
  ]
}
```

### Webhooks (outbound)

#### `POST /webhooks/subscriptions`
Creates a subscription and returns the secret once.

Request:
```json
{
  "endpoint_url": "https://example.com/webhooks/finance",
  "event_types": ["document.uploaded", "payment.completed"]
}
```

Response:
```json
{
  "request_id": "…",
  "item": { "id": "…", "endpoint_url": "https://…", "event_types": ["…"], "is_active": true },
  "secret": "whsec_…"
}
```

#### `GET /webhooks/subscriptions`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "endpoint_url": "…", "event_types": [] } ] }
```

#### `GET /webhooks/deliveries`
List webhook deliveries (history).

Response:
```json
{
  "request_id": "…",
  "items": [
    { "id": "…", "subscription_id": "…", "event_type": "document.uploaded", "status": "retrying", "attempt_count": 2 }
  ]
}
```

#### `GET /webhooks/deliveries/{delivery_id}`
Fetch a delivery including payload.

Response:
```json
{ "request_id": "…", "item": { "id": "…", "event_type": "…", "payload": { "…": "…" }, "status": "delivered" } }
```

#### `POST /webhooks/deliveries/{delivery_id}/replay`
Replay an existing delivery to its subscription endpoint (re-signs using stored encrypted secret).

Response:
```json
{ "request_id": "…", "replayed": true }
```

### Webhooks (inbound)

#### `POST /webhooks/inbound/{org_id}/{subscription_id}`
Headers:
- `X-Webhook-Signature: <hex>`

Body:
- Any JSON payload from an external system.

Response:
```json
{ "status": "ok", "ingestion_record_id": "…" }
```

### Sync jobs

#### `POST /sync/jobs`
Request:
```json
{ "connector_id": "…", "sync_type": "bank.statement.sync", "metadata": { "from": "2026-01-01" } }
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "status": "queued" } }
```

#### `GET /sync/jobs`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "status": "queued" } ] }
```

### API Keys

#### `POST /api-keys`
Request:
```json
{ "name": "my-connector", "scopes": ["webhooks:write", "sync:write"] }
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "name": "my-connector" }, "api_key": "cbk_…" }
```

#### `GET /api-keys`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "name": "my-connector", "is_active": true } ] }
```

#### `POST /api-keys/{api_key_id}/revoke`
Response:
```json
{ "request_id": "…", "item": { "id": "…", "is_active": false } }
```

#### `POST /api-keys/{api_key_id}/rotate`
Rotate an API key (revokes old key, creates a new one; raw key returned once).

Response:
```json
{ "request_id": "…", "item": { "id": "…", "name": "…" }, "api_key": "cbk_…" }
```

### Ingestion records

#### `POST /ingestion`
Request:
```json
{ "source_type": "email", "source_reference": "message-id-123", "payload": { "subject": "Invoice" } }
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "status": "received" } }
```

#### `GET /ingestion`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "source_type": "email", "status": "received" } ] }
```

---

## Frontend / integration notes

- **Secrets are returned only once** (webhook secrets, API keys). UI must store them.
- **Do not log credentials**. Send them once to create connector; never display again.
- OCR provider selection remains controlled by env/config, but provider implementations live behind Module 7 connectors.
- **API key auth**: Module 7 keys use prefix `cbk_` and can be passed via `Authorization: Bearer cbk_…`
- **Webhook delivery ops**: UIs/ops tools can list deliveries and replay failed ones via the new deliveries endpoints.

