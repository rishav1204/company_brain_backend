# Agentic Platform — FLORA Vision

**Positioning:** FLORA = Finance AI Operating System. ERP is the deterministic execution substrate; **M38 Platform AI Runtime** is the agentic layer users interact with.

---

## Cursor analogy

| Cursor | FLORA M38 |
|--------|-----------|
| Workspace files | WorldState (screen, entity, fiscal context) |
| Relevant file context | Platform Context Engine (dynamic retrieval per prompt) |
| Terminal output | Observer (tool results, policy denials) |
| Plan before edit | GoalPlanner + PlanMetadata preview |
| Accept / Apply | ApprovalEngine (human_approved) |
| Multi-file refactor | ExecutionGraph (cross-module DAG) |
| Fix build errors | SelfCorrection (alternatives) |
| Undo | RollbackManager (compensation tools) |
| Background tasks | GoalManager + scheduler + events |

---

## Implementation status (Phases 0–7)

| Phase | Status | Deliverables |
|-------|--------|--------------|
| 0 | Done | PLATFORM_DATA_FLOWS, 10 golden paths, EVENT_CONSUMER_MATRIX, M38 spec |
| 1 | Done | GoalPlanner, ExecutionGraph, Observer loop, migration 069, APIs |
| 2 | Done | 156 ERP tools via declarative catalog |
| 3 | Done | Copilot chat, plan preview fields, unified approval queue API |
| 4 | Done | GoalManager create_or_resume, scheduler hooks, M27 outcome write |
| 5 | Done | SelfCorrection alternatives, RollbackManager + forensics |
| 6 | Done | 9-step period close, checkpoint/resume API |
| 7 | Done | M29→M38 delegate, M37 billing per turn/tool, audit per step |
| 8 | Done | Platform Context Engine: intent → retrieval → compression → read answers |

Frontend shell spec: [`FRONTEND_COPILOT_INTEGRATION.md`](FRONTEND_COPILOT_INTEGRATION.md)  
Context engine spec: [`PLATFORM_CONTEXT_ENGINE.md`](PLATFORM_CONTEXT_ENGINE.md)

---

## Feasibility matrix

| Capability | Before M38 | After M38 |
|------------|------------|-----------|
| Architecture | Module agents + linear plan | Goal planner + dynamic graph + observe loop |
| Tools | ~8 agent tools | 156 ERP tools |
| World state | entity_id only | Full screen + fiscal context |
| Event autonomy | 6 fixed M29 agents | GOAL_TRIGGER_MAP + scheduler |
| Rollback | Forensics read-only | Compensation undo DAG |
| Long-running | Single workflow | Checkpoint/resume goal runs |

~70% of infrastructure already existed (ERP modules, memory, graph, policy, workflows, events, invoice pipeline). M38 adds the **missing orchestration shape**.

---

## User capabilities (with approval)

- State multi-module goals in one prompt ("buy laptops → PO → GRN → inventory")
- See execution graph and plan metadata before approving
- Undo compensatable steps
- Receive proactive plans from ERP events (overdue AR, liquidity alerts)

## Still forbidden (by design)

- Auto-post journals
- Execute bank payments without workflow
- File GST
- Bypass SoD / maker-checker
- Silent ledger mutation

See [`forbidden_actions.py`](../backend/apps/api/app/modules/finance_os/agents/orchestrator/forbidden_actions.py).
