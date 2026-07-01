# M38 — Platform AI Runtime

**Status:** Phase 1 foundation (goal planner + execution graph + observe loop)  
**Migration:** `backend/migrations/069_finance_os_platform_ai_runtime.sql`  
**Package:** `backend/apps/api/app/modules/finance_os/platform_ai_runtime/`

M38 is the **Cursor-style orchestration layer** for FLORA: users state goals in natural language (or events trigger goals silently), the runtime builds an execution DAG, runs ERP tools with policy gates, observes results, and continues until complete or blocked.

M29 domain agents remain as a **compatibility shim**; new work targets M38.

---

## Architecture (5 runtime roles)

| Role | Module | Responsibility |
|------|--------|----------------|
| GoalPlanner | `engine/goal_planner.py` | NL → ExecutionGraph + PlanMetadata |
| Executor | `services/executor.py` | Single tool invocation |
| Observer | `engine/observer.py` | Tool result → Observation |
| Recovery | `engine/self_correction.py`, `engine/rollback_manager.py` | Retry, alternatives, undo DAG |
| GoalManager | `goals/goal_manager.py` | Persistent goals, event triggers |

**Tools perform work; agents do not.**

---

## API

Base paths: `/api/v1/finance-os/runtime`, `/api/v1/finance-os/copilot`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/runtime/health` | Schema readiness |
| GET | `/runtime/tools` | Registered ERP tools |
| POST | `/runtime/goals` | Create goal from title/description |
| POST | `/copilot/chat` | Primary chat entry (creates/resumes goal) |
| POST | `/runtime/goals/{id}/runs/{run_id}/approve` | Approve paused plan |
| POST | `/runtime/goals/{id}/runs/{run_id}/continue` | Resume after approval |
| POST | `/runtime/goals/{id}/runs/{run_id}/undo` | Compensation rollback |
| POST | `/runtime/goals/{id}/runs/{run_id}/resume` | Resume from checkpoint |
| POST | `/runtime/goals/{id}/runs/{run_id}/alternative` | Apply blocked-step alternative |
| GET | `/runtime/approvals` | Unified M38 + M29 approval queue |
| GET | `/runtime/goals` | List goals |
| GET | `/runtime/goals/{id}` | Goal detail |

Auth: same as M29 (`require_agent_read` / `require_agent_run`).

---

## Persistence

| Table | Purpose |
|-------|---------|
| `finance_os.goals` | User/org/reactive goals, world_state, plan_metadata |
| `finance_os.goal_runs` | Execution attempts, approval state |
| `finance_os.execution_graphs` | Versioned DAG nodes + rollback strategy |
| `finance_os.runtime_observations` | Per-step observer output |

All tables RLS-scoped by `org_id`.

---

## World state

Passed from UI on each chat turn (`CopilotChatRequest.world_state`):

- `screen` — module, route, entity_type, entity_id  
- `org` — company, branch, fiscal period  
- `selection`, `active_workflows`, `permissions`, `recent_entities`

Built server-side by `context/world_state_builder.py` when omitted. Enriched by **Platform Context Engine** (`context/platform_context_engine.py`) before every planner/answer call.

---

## Platform Context Engine (Phase 8)

See [`PLATFORM_CONTEXT_ENGINE.md`](../../PLATFORM_CONTEXT_ENGINE.md).

| Stage | Module |
|-------|--------|
| Intent | `context/intent_engine.py` |
| Entity resolution | `context/entity_resolver.py` |
| Retrieval plan | `context/context_planner.py` |
| Multi-source fetch | `context/retrieval_orchestrator.py` |
| Ranking + compression | `context/context_ranker.py`, `context_compressor.py` |
| Read answers | `context/answer_synthesizer.py` |
| Working memory | `context/working_memory.py` + migration `070_*` |

Read/analysis intents return `mode: answer` without executing a retrieval DAG.

---

## Event autonomy

`events/event_listener.py` → `_consume_goal_triggers` in `legacy_handlers.py`.

| Event | Goal template |
|-------|---------------|
| `invoice.due` | collections_followup |
| `invoice.anomaly_detected` | ap_review |
| `liquidity_alert.created` | treasury_advisory |
| `erp.period.close.requested` | period_close |
| `reconciliation.exception.created` | recon_review |
| `grn.confirmed` | inventory_received |

Gated by M37 `gate_ai_event(feature="agents")`.

---

## Safety

- Forbidden tools unchanged: `finance_os/agents/orchestrator/forbidden_actions.py`
- Mutating tools require `human_approved=True` or pause at `pending_approval`
- Every run writes M4 audit via `audit_repo.create_log(event_type="m38.goal.run")`

---

## Migration from M29

| M29 | M38 |
|-----|-----|
| 6 domain agent classes | Planner + ToolRegistry |
| `agent_orchestration_pipeline.run()` | `runtime_service.chat()` |
| `EVENT_AGENT_MAP` | `GOAL_TRIGGER_MAP` |
| `/finance-os/agents/run` | `/finance-os/copilot/chat` |

---

## Tool Registry (Phase 2)

**156 tools** registered via declarative catalog:

- **Read (119):** procurement, inventory, AP, AR, GL, COA, journals, vouchers, banking, treasury, reconciliation, fiscal, tax, expenses, assets, reporting, compliance, consolidation, finance_os intelligence
- **Draft/submit (33):** create PO/GRN/requisition, AP/AR invoices, journal drafts, vouchers, claims, assets, payment requests, fiscal close, GST/TDS return generation
- **Custom (4):** confirm_grn, cancel_grn, inventory receive, deactivate_item

Tests: `test_platform_ai_runtime_tools_phase2.py`

```bash
# Apply migration
psql $DATABASE_URL -f backend/migrations/069_finance_os_platform_ai_runtime.sql

# Run tests
cd backend/apps/api && .venv/Scripts/python.exe -m pytest app/modules/finance_os/platform_ai_runtime/tests/ -q
```
