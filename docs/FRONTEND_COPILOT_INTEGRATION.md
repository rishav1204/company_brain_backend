# Frontend Copilot Integration — Platform AI Runtime (M38)

**Audience:** Frontend team (`new_project_frontend`)  
**Backend base:** `/api/v1/finance-os/copilot` and `/api/v1/finance-os/runtime`

This document defines the API contract for the Cursor-style Platform Copilot shell. Implementation lives in the separate frontend repo; this backend repo provides the runtime APIs.

---

## Components to build

| Component | Purpose |
|-----------|---------|
| `PlatformCopilotPanel` | Chat drawer / command palette entry |
| `ActionPlanCard` | Plan preview: reasoning, confidence, risk, approval points, rollback |
| `ExecutionGraphViewer` | DAG progress with node statuses |
| `ApprovalQueue` | Unified M38 + M29 pending items |
| `UndoButton` | Trigger compensation rollback |

---

## World state passthrough

Every chat turn must send `world_state` from the active screen:

```json
{
  "message": "Approve this invoice",
  "goal_id": "optional-for-follow-up-turns",
  "world_state": {
    "screen": {
      "module": "M11_AP",
      "route": "/finance/ap/invoices/inv-123",
      "entity_type": "invoice",
      "entity_id": "inv-123",
      "title": "Invoice INV-10234",
      "breadcrumb": "AP > Invoices > INV-10234"
    },
    "org": {
      "company_id": "...",
      "branch_id": "...",
      "fiscal_period_id": "...",
      "fiscal_period_open": true
    },
    "selection": { "vendor_id": "..." },
    "active_workflows": [],
    "permissions": ["ap.read", "ap.approve"]
  }
}
```

This enables "approve **this**" without re-specifying entity IDs.

---

## Primary API flow

### 1. Chat (create goal + plan)

`POST /api/v1/finance-os/copilot/chat`

Response includes:
- `goal_id`, `goal_run_id`
- `status`: `plan_pending_approval` | `executing` | `completed` | `blocked` | `failed`
- `mode`: `answer` | `plan` | `executing` | `completed` | `plan_pending_approval` | `blocked` | `failed`
- `plan`: confidence, risk_level, reasoning, approval_points, rollback_strategy
- `graph_nodes`: DAG steps with statuses (action/workflow intents)
- `progress_percent`, `pending_approval_nodes`, `rollback_chain`
- `approval_required`: boolean
- `sources`: retrieval citations (read/analysis answers)
- `context_summary`: intent + summary keys (optional debug)

**Read/analysis questions** (e.g. "How much GST last quarter?") return `mode: answer` with a natural-language `assistant_message` — no approval DAG unless the user asks for an action.

### 2. Approve plan

`POST /api/v1/finance-os/runtime/goals/{goal_id}/runs/{run_id}/approve`

### 3. Resume checkpoint (long-running goals)

`POST /api/v1/finance-os/runtime/goals/{goal_id}/runs/{run_id}/resume`

Or chat with `goal_id` and message `"continue"`.

### 4. Apply alternative (blocked step)

`POST /api/v1/finance-os/runtime/goals/{goal_id}/runs/{run_id}/alternative`

```json
{ "alternative_index": 0, "approved_by": "user@example.com" }
```

### 5. Undo

`POST /api/v1/finance-os/runtime/goals/{goal_id}/runs/{run_id}/undo`

```json
{ "steps": 1 }
```

### 6. Approval queue (M38 + M29)

`GET /api/v1/finance-os/runtime/approvals`

Returns items with `source`: `m38` or `m29`.

---

## UI states

| Response status | UI action |
|-----------------|-----------|
| `answer` (mode) | Render copilot answer + sources panel |
| `plan_pending_approval` | Show ActionPlanCard + Approve button |
| `executing` | Show ExecutionGraphViewer with progress bar |
| `blocked` | Show alternatives from last observation |
| `completed` | Success summary + optional undo |
| `failed` | Error + retry or new goal |

---

## Auth

Same as M29 agents: `require_agent_run` for mutations, `require_agent_read` for list/approvals.

Dev credentials: `admin@example.com` / `admin-password`, org `11111111-1111-4111-8111-111111111111`.

---

## Related docs

- [`PLATFORM_CONTEXT_ENGINE.md`](PLATFORM_CONTEXT_ENGINE.md)
- [`ERP_MODULES/M38_platform_ai_runtime.md`](ERP_MODULES/M38_platform_ai_runtime.md)
- [`DATA_FLOWS/09_agent_execution.md`](DATA_FLOWS/09_agent_execution.md)
- [`AGENTIC_PLATFORM.md`](AGENTIC_PLATFORM.md)
