# M29 — AI Agent Orchestration Layer

Finance OS module that orchestrates domain agents (AP, reconciliation, GST, close, collections, treasury) by unifying M25–M28 context, scoring confidence, persisting recommendations, and launching workflows only — never direct ledger/payment/GST filing.

## API

Base path: `/api/v1/finance-os/agents`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Module health + schema readiness |
| GET | `/catalog` | Registered agents and capabilities |
| POST | `/run` | Run agent via orchestration pipeline |
| GET | `/executions` | List agent executions |
| GET | `/executions/{id}` | Execution detail + recommendations |
| GET | `/recommendations` | List recommendations |
| GET | `/recommendations/{id}` | Recommendation detail |
| GET | `/status` | Org agent activity summary |
| POST | `/workflow` | Launch workflow from recommendation |
| POST | `/ap/run` | AP agent shortcut |
| POST | `/reconciliation/run` | Reconciliation agent shortcut |
| POST | `/gst/run` | GST agent shortcut |
| POST | `/close/run` | Close agent shortcut |
| POST | `/collections/run` | Collections agent shortcut |

Platform routes `/api/v1/agents/run` delegate to M29 when `agent_type` is a Finance OS agent.

## Persistence

Migration `054_finance_os_agent_orchestration.sql`:

- `finance_os.agent_executions` — canonical execution audit (links to `agent_runs` via `platform_run_id`)
- `finance_os.agent_recommendations` — confidence-scored recommendations with workflow refs

## Golden rule

Agents may observe, analyze, recommend, prepare, and launch workflows. They must **never** post journals, execute payments, file GST, approve transactions, or bypass governance.

Forbidden tools are blocked in `forbidden_actions.py` and `langgraph_runner.tool_adapter`.

## Events

- `agent.started`
- `agent.completed`
- `agent.recommendation.created`
- `agent.workflow.created`

Domain ERP events auto-trigger agents via `_consume_agents_trigger` in `event_consumers.py`.

## Bootstrap

```bash
python backend/scripts/bootstrap_finance_os_agents.py --org-id <uuid>
```
