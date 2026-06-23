# Module 5 — Notification & Communication Engine

**Status:** v1.2 — blueprint-complete (migrations `018`, `019`)

This document is the **UI integration spec** for Notification + Action Center.

---

## Architecture (how to think about it)

**Hard rule:** business logic (ERP/workflows/AI/governance) must **emit domain events** and never call email/WhatsApp/SMS directly.

```
Domain event
  → Event Bus (Module 3)
    → Notification Engine (Module 5)
      → template resolve (DB first, file fallback)
      → notifications.notifications row
      → queue delivery (async)
      → provider send + delivery_logs + audit
      → realtime toast into Action Center (SSE)
```

---

## Where templates live (email/in_app/etc.)

Templates are configured in two layers:

- **DB (primary)**: `notifications.templates` (seeded in `018`, extended in `019`).
- **File fallback**: `backend/apps/api/app/modules/platform/notifications/templates/email/*.txt`

Renderer supports:

- `{{variables}}`
- conditional blocks: `{% if field %}...{% endif %}`
- masking for sensitive variables: `pan`, `aadhaar`, `account_number`, `bank_account`, `ifsc`

Email sending:

- **Resend** (free tier) if `RESEND_API_KEY` is set
- else SMTP (if configured)
- else dev console log

```env
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=onboarding@resend.dev
```

---

## Database schema (notifications.*)

- **`notifications.notifications`**: master record (status, priority, snooze, ack)
- **`notifications.delivery_logs`**: retryable/auditable delivery attempts
- **`notifications.templates`**: org templates + platform defaults (org_id NULL)
- **`notifications.preferences`**: per-user per-channel preferences + `quiet_hours`
- **`notifications.subscriptions`**: realtime channel subscriptions
- **`notifications.digest_queue`**: digest batching queue

---

## API base

All endpoints are under **`/api/v1`** and require auth (request context provides `org_id`, `user_id`, `request_id`).

---

## Notifications API (history + badge + ack + snooze)

### `GET /notifications`

Query params:

- `unread_only` (bool, default `false`)
- `notification_type` (string, optional)
- `channel` (string, optional)
- `priority` (string, optional)
- `limit` (int, default `50`, max `200`)

Response:

```json
{
  "request_id": "req_...",
  "items": [
    {
      "id": "uuid",
      "notification_type": "approval_request",
      "channel": "email",
      "subject": "Approval required: INV-1001",
      "body": "Hi ...",
      "status": "sent",
      "priority": "high",
      "related_entity_type": "workflow_instance",
      "related_entity_id": "uuid-or-null",
      "acknowledged_at": null,
      "created_at": "2026-05-27T...",
      "sent_at": "2026-05-27T..."
    }
  ]
}
```

Notes:

- Snoozed notifications are automatically excluded until `snoozed_until <= NOW()`.

### `GET /notifications/unread-count`

Response:

```json
{ "request_id": "req_...", "unread_count": 3 }
```

### `POST /notifications/{id}/acknowledge`

Response:

```json
{ "request_id": "req_...", "acknowledged": true }
```

### `POST /notifications/{id}/snooze`

Request:

```json
{ "until": "2026-05-28T10:00:00+00:00" }
```

Response:

```json
{ "request_id": "req_...", "snoozed": true }
```

---

## Preferences API (per-user channel/type + quiet hours)

### `GET /preferences`

Response:

```json
{
  "request_id": "req_...",
  "items": [
    {
      "channel": "email",
      "notification_type": "approval_request",
      "enabled": true,
      "quiet_hours": { "start": "22:00:00", "end": "07:00:00" }
    }
  ]
}
```

### `POST /preferences`

Request:

```json
{
  "channel": "email",
  "notification_type": "approval_request",
  "enabled": true,
  "quiet_hours": { "start": "22:00:00", "end": "07:00:00" }
}
```

Response:

```json
{ "request_id": "req_...", "preference": { "id": "uuid", "channel": "email", "notification_type": "approval_request", "enabled": true } }
```

Quiet hours enforcement:

- during quiet hours, email/whatsapp/sms are suppressed for that type/channel; **`in_app` still allowed**.

---

## Templates API (admin)

### `GET /templates`

Response:

```json
{
  "request_id": "req_...",
  "items": [
    { "id": "uuid", "template_key": "approval_request", "channel": "email", "subject_template": "Approval required: {{entity_label}}", "is_active": true, "created_at": "..." }
  ]
}
```

### `POST /templates`

Request:

```json
{
  "template_key": "approval_request",
  "channel": "email",
  "subject_template": "Approval required: {{entity_label}}",
  "body_template": "Hi {{recipient_name}} ...",
  "variables": ["recipient_name", "entity_label", "amount"]
}
```

Response:

```json
{ "request_id": "req_...", "template": { "id": "uuid", "template_key": "approval_request", "channel": "email" } }
```

### `PUT /templates/{id}`

Request:

```json
{ "subject_template": "New subject", "body_template": "New body", "is_active": true }
```

Response:

```json
{ "request_id": "req_...", "template": { "id": "uuid", "template_key": "approval_request", "channel": "email", "is_active": true } }
```

---

## Realtime / Action Center API (SSE)

This reuses existing realtime infra (Module 2 hub) and exposes an Action Center feed.

### Channels

- `action_center` (default)
- `workflow_updates`
- `approval_queue`
- `risk_alerts`
- `compliance_alerts`
- `payment_updates`

### `POST /realtime/subscribe`

Request:

```json
{ "channel_key": "approval_queue" }
```

Response:

```json
{ "request_id": "req_...", "subscription": { "id": "uuid", "channel_key": "approval_queue" } }
```

### `GET /realtime/action-center`

Query params:

- `cursor` (int, default `0`)
- `channel` (string, optional)

Response:

```json
{
  "request_id": "req_...",
  "channel": "approval_queue",
  "events": [
    {
      "event_type": "notification.approval_request",
      "channel": "action_center",
      "priority": "high",
      "title": "Approval required: INV-1001",
      "body": "Approval required: INV-1001",
      "notification_id": "uuid",
      "toast": true,
      "metadata": { "related_entity_type": "workflow_instance", "related_entity_id": "..." }
    }
  ],
  "next_cursor": 12
}
```

### `GET /realtime/action-center/sse`

Query params:

- `channel` (string, optional)

Response is an **SSE stream**:

```
data: {"event_type":"notification.approval_request", ...}\n\n
```

UI integration notes:

- treat each SSE `data:` payload as a **toast candidate** when `toast: true`
- use `notification_id` to dedupe on the client if needed

---

## Provider webhooks (placeholders for later automation)

### `POST /webhooks/notifications/resend`
### `POST /webhooks/notifications/whatsapp`

Both currently **ack** and log payloads (safe placeholders).

---

## Domain events other modules should emit (the contracts)

This is the critical integration point for M1–M4 and future modules.

### Approval requested (Workflow Engine)

Event type: `approval.requested`

Payload (minimum for correct targeting):

```json
{
  "approval_id": "uuid",
  "workflow_instance_id": "uuid",
  "approver_user_id": "uuid",
  "approver_email": "approver@company.com",
  "entity_label": "INV-1001",
  "amount": "500000"
}
```

### Workflow approval reminder

Event type: `workflow.approval.reminder`

```json
{
  "workflow_instance_id": "uuid",
  "step_key": "approve_invoice",
  "recipient_user_id": "uuid",
  "recipient_email": "approver@company.com",
  "entity_label": "Workflow <id>",
  "message": "Step approve_invoice due soon"
}
```

### Workflow escalated

Event type: `workflow.escalated`

```json
{
  "workflow_instance_id": "uuid",
  "escalation_id": "uuid",
  "recipient_user_id": "uuid",
  "reason": "sla_breach"
}
```

### SLA breached

Event type: `sla.breached`

```json
{ "workflow_instance_id": "uuid", "step_id": "uuid" }
```

### Policy violation (Governance)

Event type: `policy.violation.detected`

```json
{
  "compliance_type": "policy.violation",
  "status": "flagged",
  "summary": "Policy X violated",
  "related_entity_type": "payment",
  "related_entity_id": "uuid"
}
```

### Compliance alert + GST deadline

Event type: `compliance.alert.generated`

```json
{ "compliance_type": "gst.delayed_filing", "status": "overdue" }
```

Event type: `gst.deadline.approaching`

```json
{ "deadline": "2026-05-31", "compliance_type": "gst" }
```

### Risk + suspicious activity (AI/Governance)

Event type: `payment.risk.detected`

```json
{ "risk": { "reason": "duplicate_vendor_payment", "amount": 500000 }, "summary": "{...string...}" }
```

Event type: `suspicious.activity.detected`

```json
{ "summary": "high-risk payment pattern", "amount": 500000, "severity": "high" }
```

### Reconciliation suggestions (AI)

Event type: `ai.reconciliation.suggested`

```json
{ "entity_label": "REC-2026-05-27", "summary": "3 unmatched bank lines..." }
```

---

## Delivery lifecycle events emitted by Module 5

- `notification.sent`
- `notification.delivered`
- `notification.failed`

These events can be used by analytics/ops dashboards and downstream automation.

---

## Migrations

```powershell
psql $POSTGRES_DSN -f backend/migrations/018_notifications.sql
psql $POSTGRES_DSN -f backend/migrations/019_notifications_templates_extended.sql
```

---

## UI smoke test (recommended)

1) Subscribe to SSE: `GET /api/v1/realtime/action-center/sse`
2) Trigger a workflow approval (emits `approval.requested`)
3) Verify:
   - `GET /api/v1/notifications/unread-count` increments
   - SSE emits `toast: true` events
   - `POST /api/v1/notifications/{id}/acknowledge` clears badge
