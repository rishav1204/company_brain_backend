# M10 — Journal Engine + Accounting Transaction Orchestration

## Purpose
Module 10 is the **accounting transaction orchestration layer** above Module 9 (GL).

| Layer | Role |
|-------|------|
| **GL (M9)** | Immutable financial truth (`erp.ledger_entries`) |
| **Journal Engine (M10)** | Create, validate, approve, post, reverse accounting transactions |

## Database (schema: `erp.*`)
| Migration | Purpose |
|-----------|---------|
| `031_erp_journal_engine.sql` | Core journal tables |
| `032_erp_journal_immutability.sql` | Status constraints + immutability triggers |

### Core tables
| Table | Purpose |
|-------|---------|
| `erp.journals` | Transaction container (mutable until posted) |
| `erp.journal_lines` | Debit/credit lines (XOR constraint) |
| `erp.recurring_journals` | Recurring templates |
| `erp.journal_reversals` | Reversal tracking |
| `erp.accrual_entries` | Accrual records linked to journals |

### Journal lifecycle
`draft` → `pending_approval` → `approved` → `posted` → `reversed` / `cancelled`

**Immutable after posting** — corrections via reversal journals only (DB triggers enforce this).

## Posting flow
```
Draft journal → validation → approval → atomic posting orchestrator → GL → ledger entries
```

---

## API Reference (prefix: `/api/v1/erp`)

All responses include `request_id` from the request context.

### Journals

#### `POST /erp/journals` — Create draft
**Auth:** `require_finance_journal_admin`

**Request body:**
```json
{
  "journal_type": "general",
  "posting_date": "2026-06-05",
  "description": "Office supplies",
  "source_type": "manual",
  "source_id": null,
  "currency_code": "INR",
  "exchange_rate": 1.0,
  "company_id": null,
  "idempotency_key": null,
  "lines": [
    {
      "account_id": "uuid",
      "debit_amount": 1000.0,
      "credit_amount": 0,
      "line_description": "Expense",
      "cost_center_id": null,
      "tax_code": null,
      "reference_type": null,
      "reference_id": null
    },
    {
      "account_id": "uuid",
      "debit_amount": 0,
      "credit_amount": 1000.0,
      "line_description": "Payable"
    }
  ]
}
```

**Response:**
```json
{
  "request_id": "req-...",
  "item": {
    "journal": {
      "id": "uuid",
      "journal_number": "JN-...",
      "journal_type": "general",
      "journal_status": "draft",
      "posting_date": "2026-06-05",
      "description": "Office supplies",
      "source_type": "manual",
      "source_id": null,
      "currency_code": "INR",
      "exchange_rate": 1.0,
      "created_by": "uuid",
      "ai_confidence": {},
      "company_id": null,
      "created_at": "..."
    },
    "lines": [ "..."]
  }
}
```

#### `GET /erp/journals` — List journals
**Query:** `journal_status`, `journal_type`, `limit` (1–500), `offset`

**Response:**
```json
{
  "request_id": "req-...",
  "items": [
    {
      "id": "uuid",
      "journal_number": "JN-...",
      "journal_type": "purchase",
      "journal_status": "draft",
      "posting_date": "2026-06-05",
      "description": "...",
      "created_by": "uuid",
      "created_at": "..."
    }
  ]
}
```

#### `GET /erp/journals/{journal_id}` — Get journal with lines
**Response:** Same shape as create `item`.

#### `PUT /erp/journals/{journal_id}` — Update draft
**Auth:** `require_finance_journal_admin`

**Request body:** (all optional)
```json
{
  "posting_date": "2026-06-06",
  "description": "Updated",
  "journal_type": "adjustment",
  "lines": [ "..."]
}
```
Editing lines clears `ai_confidence.requires_review` (marks finance-reviewed).

#### `POST /erp/journals/{journal_id}/cancel` — Cancel non-posted journal
**Response:** `{ "request_id", "item": { journal + lines } }`

#### `POST /erp/journals/ai/from-document` — AI draft (never auto-posts)
**Request body:**
```json
{
  "document_id": "uuid",
  "extracted_data": { "subtotal": 1000, "cgst": 90, "sgst": 90, "vendor_name": "ACME" },
  "posting_date": "2026-06-05",
  "journal_type": "purchase"
}
```
**Response:** Draft journal with `ai_confidence` scores. Low confidence sets `requires_review: true`.

---

### Approval + Posting

#### `GET /erp/journals/approval-queue` — Pending approval queue
**Auth:** `require_finance_journal_admin`

**Query:** `limit`, `offset`

**Response:**
```json
{
  "request_id": "req-...",
  "items": [ "...pending_approval journals..." ],
  "count": 3
}
```

#### `POST /erp/journals/{journal_id}/submit` — Submit for approval
**Auth:** `require_finance_journal_admin` + `evaluate_access(journal.submit)`

**Response:**
```json
{
  "request_id": "req-...",
  "item": { "journal_id": "uuid", "journal_status": "pending_approval" }
}
```

#### `POST /erp/journals/{journal_id}/approve` — Approve
**Auth:** `require_finance_journal_admin` + `evaluate_access(approve)` + maker-checker

Blocks if `ai_confidence.requires_review` is true (use mark-reviewed or edit lines first).

**Response:**
```json
{
  "request_id": "req-...",
  "item": { "journal_id": "uuid", "journal_status": "approved", "approved_by": "uuid" }
}
```

#### `POST /erp/journals/{journal_id}/reject` — Reject to draft
**Response:**
```json
{
  "request_id": "req-...",
  "item": { "journal_id": "uuid", "journal_status": "draft", "rejected_by": "uuid" }
}
```

#### `POST /erp/journals/{journal_id}/mark-reviewed` — Clear AI review flag
**Request body:** `{ "comment": "Reviewed by finance" }`

**Response:** `{ "request_id", "item": { journal + lines }, "comment": "..." }`

#### `POST /erp/postings/{journal_id}/post` — Post approved journal to GL
**Auth:** `require_finance_journal_admin` + `evaluate_access(post_journal)`

Atomic: GL batch + journal status update in **one DB transaction**.

**Response:**
```json
{
  "request_id": "req-...",
  "item": {
    "journal_id": "uuid",
    "journal_status": "posted",
    "ledger_batch_id": "uuid",
    "gl_result": { "batch": {}, "totals": { "debit": 1000, "credit": 1000 } }
  }
}
```
Idempotent if already posted: `{ "idempotent": true, ... }`

#### `POST /erp/postings/batch` — Batch post (up to 50 journals)
**Request body:**
```json
{ "journal_ids": ["uuid1", "uuid2"] }
```
**Response:**
```json
{
  "request_id": "req-...",
  "items": [ { "journal_id": "...", "journal_status": "posted" }, { "journal_id": "...", "error": "...", "journal_status": "failed" } ],
  "count": 2
}
```

---

### Reversals

#### `POST /erp/reversals/{journal_id}` — Reverse posted journal
**Auth:** `require_finance_journal_admin` + `evaluate_access(journal.post)`

**Request body:**
```json
{
  "reversal_reason": "Duplicate entry",
  "approver_id": null
}
```
`approver_id` optional — separate approver for maker-checker on reversal journal.

**Response:**
```json
{
  "request_id": "req-...",
  "item": {
    "original_journal_id": "uuid",
    "reversal_journal_id": "uuid",
    "post_result": { "journal_status": "posted", "ledger_batch_id": "uuid" }
  }
}
```

---

### Recurring journals

#### `POST /erp/journals/recurring` — Create template
**Request body:**
```json
{
  "template_name": "Monthly rent",
  "frequency": "monthly",
  "next_run_date": "2026-07-01",
  "company_id": null,
  "journal_template": {
    "journal_type": "general",
    "description": "Office rent",
    "lines": [ "..."]
  }
}
```
Frequencies: `daily`, `weekly`, `monthly`, `quarterly`, `yearly`

#### `GET /erp/journals/recurring` — List templates
**Query:** `active_only` (default `true`)

#### `POST /erp/journals/recurring/{recurring_id}/deactivate`

#### `POST /erp/journals/recurring/run-due` — Generate drafts from due templates
**Query:** `as_of_date` (optional, default today)

Also runs automatically on `scheduler.tick`.

### Scheduler end-to-end orchestration
On `scheduler.tick`, when due recurring journals / accrual reversals are generated, the system now follows the blueprint flow:

`draft → submit_for_approval → workflow started (entity_type=journal, metadata.journal_id) → (after approval) workflow.step.system_task(step_key=journal.post) → post to GL`

Maker-checker is preserved because the scheduler **does not auto-approve**.

---

### Accruals

#### `POST /erp/accruals` — Create accrual + draft journal
**Request body:**
```json
{
  "accrual_type": "utilities",
  "accrual_date": "2026-05-31",
  "estimated_expense": 5000,
  "paid_amount": 0,
  "amount": null,
  "expense_account_id": "uuid",
  "liability_account_id": "uuid",
  "source_reference": null,
  "reversal_date": "2026-06-15",
  "company_id": null
}
```
Formula: `amount = estimated_expense - paid_amount` (or pass explicit `amount`).

**Response:**
```json
{
  "request_id": "req-...",
  "item": {
    "accrual": { "id": "uuid", "accrual_type": "utilities", "amount": 5000, "reversal_date": "2026-06-15" },
    "journal": { "journal": {}, "lines": [] },
    "computed_amount": 5000
  }
}
```

#### `GET /erp/accruals` — List accruals

Accrual reversals auto-generate draft journals on `scheduler.tick` when `reversal_date` is due.

---

## Validation (non-negotiable)
| Rule | Enforced at |
|------|-------------|
| Double-entry: debits = credits | submit, approve, post |
| Lines: debit XOR credit | submit, approve, post |
| Accounts: active + postable | submit, approve, post |
| Fiscal period: open | submit, approve, post |
| GST: tax_code ↔ gst account mapping | post |
| AI low confidence → finance review | approve, post |
| Maker-checker | approve, post, reverse |
| Governance `evaluate_access` | submit, approve, post, reverse |
| Posted immutability | DB triggers + service guards |

## Events

### Emitted
| Event | When |
|-------|------|
| `journal.created` / `erp.journal.created` | Draft created |
| `journal.approved` / `erp.journal.approved` | Approved |
| `journal.posted` / `erp.journal.posted` | Posted to GL |
| `journal.reversed` / `erp.journal.reversed` | Reversed |
| `erp.journal.posting.completed` | Posting latency telemetry |

### Consumed
| Event | Action |
|-------|--------|
| `invoice.extracted`, `ocr.completed` | AI draft journal |
| `approval.completed`, `workflow.approved` | Approve journal |
| `payment.completed` | Post journal (must be approved) |
| `workflow.step.system_task` (`journal.post`) | Approve + post (skips if AI review required) |
| `scheduler.tick` | Recurring `run-due` + accrual reversals |

### COA side-effect
`journal.posted` → updates `erp.account_usage.used_in_journals` per line account.

## Realtime (Action Center)
Toast notifications pushed on:
- `journal.approved`
- `journal.posted`
- `journal.reversed`

## Observability metrics
| Metric | Description |
|--------|-------------|
| `journal_postings` | Successful posts |
| `journal_posting_failures` | Failed posts |
| `journal_posting_latency_ms` | Posting duration |
| `journal_reversals` | Reversal count |
| `journal_validation_failures` | Validation rejections |
| `journal_approvals` | Approvals |
| `journal_submissions` | Submissions |
| `journal_ai_low_confidence` | AI drafts flagged for review |

## AI safety rule
AI **prepares** draft journals with confidence scoring.
AI **never** silently posts to GL.

## Module structure
```
modules/erp/journals/
├── routes/          journal, posting, reversal, recurring, accrual
├── services/        journal, approval, posting_orchestrator, reversal, accrual, recurring, ai, validation, template, realtime
├── repositories/    journal, journal_line, recurring, reversal, accrual
├── validators/      journal, balance, posting, reversal, gst
├── engine/          journal, approval, reversal, accrual, recurring (facades)
├── ai/              journal_generator, confidence_engine, ledger_suggester, anomaly_checker
├── events/          journal_events, posting_events
├── schemas/         journal_schema, reversal_schema, recurring_schema
└── tests/
```

## Blueprint compliance audit (post-gap-closure)

| Requirement | Status |
|-------------|--------|
| Journal lifecycle (draft→posted→reversed) | ✅ |
| Double-entry validation | ✅ |
| Atomic journal+GL posting | ✅ |
| Reversal via reversal journals | ✅ |
| Reversal maker-checker fix | ✅ |
| GST validation at post | ✅ |
| AI confidence enforcement | ✅ |
| DB immutability triggers | ✅ |
| Governance evaluate_access | ✅ |
| Approval queue API | ✅ |
| Batch posting API | ✅ |
| Recurring scheduler hook | ✅ |
| Accrual formula + auto-reversal scheduler | ✅ |
| COA journal.posted consumer | ✅ |
| workflow.approved in registry | ✅ |
| Event consumer error logging | ✅ |
| Realtime Action Center push | ✅ |
| Journal OTEL metrics | ✅ |
| Engine/validator/schema structure | ✅ |
| Unit tests | ✅ |
| Integration/load/chaos tests | ⚠️ Deferred (future hardening) |
| AP/AR/banking subledger orchestration | ⚠️ Module 11+ (by design) |
| Async posting queue worker | ⚠️ Deferred (sync API sufficient for MVP) |

## Integration with other modules
| Module | Role |
|--------|------|
| M6 Documents | OCR → AI draft journals |
| M2 Workflows | Approval routing + `journal.post` system task |
| M9 GL | Immutable posting destination |
| M8 COA | Account + GST mapping validation |
| M4 Governance | Audit + evaluate_access |
| M3 Events | Event bus integration |
| Notifications | Action Center realtime toasts |
