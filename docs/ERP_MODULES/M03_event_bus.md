# Module 3 — Event Bus + Async Execution

**Audience:** Backend, ERP, workflow, and integration teams  
**Base URL:** `http://localhost:8000/api/v1`  
**Status:** v3.1 — infrastructure complete; ERP write-path publishers deferred to Module 4 (migration `015` after `009` core IAM)

---

## Purpose

The event bus is the **asynchronous nervous system** of the Finance OS:

- Domain facts (`erp.invoice.created`) decouple ERP from workflows
- Workers process OCR, AI, reconciliation, notifications without blocking HTTP
- Retries, DLQs, and idempotency protect financial operations
- Scheduler **emits events**; workers **execute** heavy work

---

## Architecture

| Layer | Responsibility |
|-------|----------------|
| **ERP** | Emit domain facts only — never hardcode approval chains |
| **Platform event bus** | Canonical envelope, routing, persistence, webhooks |
| **Workflow engine (M02)** | Consume `erp.*` / `workflow.*` from queues |
| **Workers** | `cmd/worker.py` drains Redis Streams / lists |

**Queue backend:** `EVENT_QUEUE_BACKEND=redis_streams` (default). Falls back to Redis lists when unset.

---

## Canonical event envelope

```json
{
  "event_id": "uuid",
  "event_type": "erp.invoice.created",
  "event_version": "v1",
  "org_id": "uuid",
  "entity_type": "invoice",
  "entity_id": "uuid",
  "source": "erp.ap",
  "timestamp": "2026-05-23T10:00:00Z",
  "trace_id": "uuid",
  "actor_id": "uuid",
  "payload": {},
  "metadata": {}
}
```

**Ownership rule:** each `event_type` has one owner (`event_registry.py`). Publishing from wrong `source` returns `403`.

---

## Database (`platform.*`) — migration `015`

| Table | Purpose |
|-------|---------|
| `platform.event_store` | Replay, audit, debugging |
| `platform.idempotency_keys` | Finance-grade dedupe (`org_id` + `scope` + key) |
| `platform.webhook_subscriptions` | Outbound webhook config |
| `platform.webhook_deliveries` | Delivery log + retries |
| `platform.queue_jobs` | Job observability |

---

## Queues

### Workflow
`workflow.execution`, `workflow.approvals`, `workflow.escalations`, `workflow.sla`, `workflow.retries`

### AI
`ai.ocr`, `ai.reconciliation`, `ai.risk`, `ai.memory`, `ai.forecasting`

### Integration
`integration.gst`, `integration.bank`, `integration.webhooks`, `integration.email`

### Notifications
`notifications.email`, `notifications.whatsapp`, `notifications.push` (+ legacy `notifications.dispatch`)

### Reporting
`reports.generate`, `reports.refresh`

Every critical queue has a **`.dlq`** sibling.

---

## v3.1 additions (M3.1)

| Area | Behavior |
|------|----------|
| **Consumer retry / DLQ** | `fail_claim()` on handler exceptions — exponential backoff, then `{queue}.dlq`; emits `job.failed` / `retry.exceeded` |
| **Consumer idempotency** | `consumer_idempotency` — per `event_id` + queue in `platform.idempotency_keys` |
| **Middleware** | `validate_incoming_event` + `trace_event_processing` on publish and consume |
| **Webhooks** | `rate_limit_per_minute` enforced before enqueue |
| **Publish rate limit** | `EVENT_PUBLISH_RATE_LIMIT_PER_MINUTE` per org |
| **Realtime** | `platform_realtime_bridge` → M02 `workflow_realtime_hub` |
| **OCR** | `ai.ocr.requested` from document ingestion; `ocr_worker` processes queue |
| **Blueprint files** | `scheduler/`, `models/`, `schemas/queue_schema.py`, `bus/event_bus.py`, `priority_queue.py`, `banking_events.py`, `integration_events.py` |
| **ERP emit helpers** | Full registry coverage in `erp_events.py` — **call sites in Module 4 only** |

---

## Deferred to Module 4 (ERP)

Do **not** mark Module 3 incomplete for these — they require ERP write paths:

- `emit_invoice_created` / `emit_payment_completed` / etc. on real AP, treasury, GL APIs
- GST, bank import, Razorpay/Tally integration emitters on live connectors
- `webhook.received` on inbound provider callbacks

Module 3 provides helpers, routing, consumers, and tests; Module 4 wires publishers.

---

## ERP domain events (publish from Module 4+)

```text
erp.invoice.created      → workflow.execution (auto-start AP approval)
erp.payment.completed
erp.journal.posted
erp.gst.return.generated
erp.reconciliation.pending
```

**Helper:** `app.modules.platform.events.events.erp_events.emit_invoice_created(...)`

---

## API surface

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/events/publish` | Publish canonical event |
| `GET` | `/events/catalog` | Registered event types + owners |
| `GET` | `/events/registry/{event_type}` | Single event definition |
| `POST` | `/events/replay` | Re-publish from `event_store` |
| `GET` | `/queues` | Queue names + lag + DLQ depth |
| `POST` | `/queues/{queue}/dlq/requeue` | Admin DLQ recovery |
| `GET` | `/jobs` | `platform.queue_jobs` listing |
| `POST` | `/webhooks/subscriptions` | Create outbound webhook |
| `GET` | `/webhooks/subscriptions` | List subscriptions |
| `POST` | `/webhooks/deliveries/process` | Retry pending deliveries |

Legacy: `POST /queue/enqueue`, `GET /queue/topology`, `POST /ops/worker/run-batch`

---

## Scheduler (emit-only)

`scheduler_service` emits:

- `scheduler.sla.scan` → `workflow.sla` consumer → SLA worker
- `scheduler.escalation.scan` → escalation worker
- `scheduler.reconciliation.daily` → reconciliation worker

Run: `POST /ops/scheduler/run-once` or `cmd/scheduler.py`

---

## Webhooks

HMAC-SHA256: `X-Webhook-Signature = HMAC(secret, body)`

Subscriptions filter by `event_types[]`. Deliveries retry with backoff.

---

## Idempotency

```http
POST /events/publish
{
  "event_type": "erp.invoice.created",
  "idempotency_key": "inv-1001-create",
  ...
}
```

Stored in `platform.idempotency_keys` — replays return cached response.

---

## Module layout

```text
modules/platform/events/
  bus/          event_registry, topology, publisher, subscriber, dispatcher
  queues/       queue_manager (Redis Streams), retry_queue, dead_letter_queue
  workers/      ocr, ai, workflow, reconciliation, webhook, notification, scheduler
  services/     event_service, idempotency, webhook, scheduling, retry
  repositories/ event_store, queue_jobs
  scheduler/    cron_manager, job_registry, sla_scheduler
  models/       StoredEvent
  schemas/      event_schema, queue_schema, webhook_schema
  events/       erp_events, ai_events, banking_events, integration_events, system_events
```

---

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Required in prod |
| `EVENT_QUEUE_BACKEND` | `redis_streams` | `redis_streams` or `redis_list` |
| `EVENT_RETRY_BASE_SECONDS` | `5` | Exponential backoff base |
| `EVENT_RETRY_MAX_ATTEMPTS` | `5` | Max retries before DLQ |
| `EVENT_QUEUE_INFLIGHT_SECONDS` | `120` | Stream stale message reclaim |
| `EVENT_PUBLISH_RATE_LIMIT_PER_MINUTE` | `120` | Per-org publish throttle |

---

## Tests

```powershell
cd backend\apps\api
python -m pytest tests/test_platform_*.py tests/test_event_topology_finance_topics.py -q
```

---

## Integration with Module 2

| M02 feature | M03 dependency |
|-------------|----------------|
| Async approvals | `workflow.approvals` queue |
| SLA / escalation workers | `scheduler.*` events → `workflow.sla` / `workflow.escalations` |
| AI wait/resume | `agent.run` queue |
| ERP auto-start | `erp.invoice.created` → `workflow.execution` |

Apply migration `015` before enabling `platform_event_service` persistence.
