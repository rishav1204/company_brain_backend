# M36 — API + Webhook Platform

M36 is the **enterprise integration layer** — public/partner APIs, webhook subscriptions, HMAC signing, rate limiting, and idempotency for external systems connecting to Finance OS + ERP.

## Golden rule (non-negotiable)

| Do | Don't |
|----|-------|
| Reuse **M3 event bus**, **Redis queue/DLQ**, **M7 integrations** schema | Build a parallel event bus or `platform.api_keys` table |
| Route external mutations through **M34 policy** + **M33 audit** | Bypass governance on partner APIs |
| Use **`integrations.api_keys`** (`cbk_`) + IAM **`cb_`** keys | Store raw API keys in the database |

**Blueprint mapping:** `platform.api_keys` → `integrations.api_keys`; webhook tables → `integrations.webhook_*`.

## Persistence

Migration `061_api_gateway_platform.sql`:

- Extended `integrations.api_keys` (ip_allowlist, rate limits, key_tier)
- Extended `integrations.webhook_deliveries` (response_code, response_body)
- `platform.api_request_log`
- `platform.event_stream_adapters` (v1 stub)

Bootstrap: `python backend/scripts/bootstrap_api_gateway.py --org-id <uuid>`

## Canonical flows

**Inbound:** External app → `/api/v1/platform/*` → API key → rate limit → policy → ERP

**Outbound:** ERP event → M3 publish → `webhook_dispatcher` → HMAC POST → partner URL

Retry schedule: 1m → 5m → 15m → 1h → 6h → terminal `failed` / DLQ

## HTTP API

Prefix: `/api/v1/platform/*` (M7 `/integrations/*` remains for backward compatibility)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/platform/api-keys` | Create hashed partner key |
| GET | `/platform/api-keys` | List keys |
| DELETE | `/platform/api-keys/{id}` | Revoke |
| POST | `/platform/webhooks` | Subscribe to events |
| GET | `/platform/webhooks` | List subscriptions |
| DELETE | `/platform/webhooks/{id}` | Deactivate |
| GET | `/platform/events/catalog` | Partner-subscribable events |
| GET | `/platform/events` | Event store read |
| GET | `/platform/integrations/health` | Connector + queue health |

## Security

- API keys hashed at rest (`cbk_` prefix)
- HMAC `X-Signature` + `X-Webhook-Signature` on outbound webhooks
- Per-key IP allowlist + rate limits
- `Idempotency-Key` header → `platform.idempotency_keys`
- Inbound webhooks: public path + HMAC only

## Scope catalog

`invoice.read`, `invoice.write`, `payments.read`, `payments.write`, `reports.read`, `webhooks.manage`, `integrations.sync`, `api.keys.manage`, `admin`

## Upstream integration checklist

| Module | Integration | Status |
|--------|-------------|--------|
| M1 IAM | `cb_` / `cbk_` auth; `actor_type=api_key` in attrs | Done |
| M3 Event Bus | Single `webhook_dispatcher` on publish | Done |
| M7 Integrations | Connectors, ingestion, encrypted webhook secrets | Done |
| M22 Banking | Bank connectors + `payment.executed` events | Done |
| M25 Invoice AI | `invoice.extracted` in partner catalog | Done |
| M29 Agents | `agent.completed` in catalog | Done |
| M31 Reporting | `reports.read` scope | Done |
| M33 Audit | `api_request_log`, webhook/api event materialization | Done |
| M34 Policy | `gateway_access` on mutations | Done |
| M35 Consolidation | `consolidation.completed` in catalog | Done |
| Accounting | Tally/Zoho/SAP stub connectors | Done |

## Events emitted

`webhook.delivered`, `webhook.failed`, `api.key.created`, `api.key.revoked`, `integration.connected`

## v1 non-goals

Node/Python/Java SDK packages, live Kafka/EventBridge adapters, real Tally/SAP/Zoho API calls.
