# Platform Context Engine

The **Platform Context Engine** (PCE) is the dynamic context assembly layer inside M38. It answers: *"What information should the AI see right now?"* — not the user question itself.

## Pipeline

```
User message + WorldState (UI)
        ↓
IntentEngine          → read | action | workflow | analysis | mixed
        ↓
EntityResolver        → screen entity, selection, working memory, NL hints
        ↓
ContextPlanner        → RetrievalPlan (which sources to fetch)
        ↓
RetrievalOrchestrator → M27 memory, M28 graph, ERP bridges, documents, read tools
        ↓
ContextRanker         → top-N per source, screen-entity boost
        ↓
ContextCompressor     → token-budgeted structured summaries
        ↓
PromptAssembler       → planner block or answer prompt
        ↓
AnswerSynthesizer (read/analysis)  OR  GoalPlanner (action/workflow/mixed)
```

## Package layout

`backend/apps/api/app/modules/finance_os/platform_ai_runtime/context/`

| Module | Role |
|--------|------|
| `platform_context_engine.py` | Facade: `build()` orchestrates full pipeline |
| `intent_engine.py` | Heuristic + optional LLM intent classification |
| `entity_resolver.py` | UI + NL entity resolution |
| `context_planner.py` | Declarative source map per intent/module |
| `retrieval_orchestrator.py` | Parallel fan-out to existing bridges |
| `context_ranker.py` | Cross-source relevance ranking |
| `context_compressor.py` | Summaries + token budget |
| `prompt_assembler.py` | System + context + question templates |
| `answer_synthesizer.py` | Read-mode LLM answers |
| `working_memory.py` | Per-goal conversation state |
| `context_bridge.py` | Domain copilot integration (M32, etc.) |

## API behavior

`POST /api/v1/finance-os/copilot/chat` now routes by intent:

| Intent | Response `mode` | Behavior |
|--------|-----------------|----------|
| `read`, `analysis` | `answer` | Context built → LLM answer; no execution DAG |
| `action`, `workflow` | `executing` / `plan_pending_approval` | Context enriches planner → DAG execution |
| `mixed` | `executing` + answer prefix | Answer preview + proposed action plan |

Response fields: `sources`, `context_summary` (dev-oriented).

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `M38_CONTEXT_ENGINE_ENABLED` | `true` | Master switch |
| `M38_READ_ANSWER_MODE` | `true` | Read/analysis → answer synthesizer |
| `M38_WORKING_MEMORY` | `true` | Persist conversation state on goals |
| `M38_UNIFIED_COPILOT` | `false` | Route domain copilots through PCE |

## Persistence

Migration `070_finance_os_platform_context_conversation.sql` adds `finance_os.goals.conversation_state` for working memory across turns.

## Frontend contract

See [`FRONTEND_COPILOT_INTEGRATION.md`](../FRONTEND_COPILOT_INTEGRATION.md) — every turn must send `world_state.screen` so queries like *"Why is this pending?"* resolve without repeating entity IDs.

## Golden-path examples

### GST quarter

> How much GST did we pay last quarter?

Sources: `tax_gst.list_returns`, compliance bridge, compliance memories → compressed GST summary → answer.

### AP vendor delays

> Which vendors are getting paid late?

Sources: `ap.list_outstanding`, invoice context, graph vendor edges → ageing summary → ranked answer.

### Cash flow analysis

> Why is cash flow lower this month?

Intent: `analysis`. Sources: treasury, AR/AP outstanding, forecasting, graph → multi-section summary → causal narrative.
