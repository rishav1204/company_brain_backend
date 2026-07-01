# Golden Path 09 — M38 Agent Execution Loop

```text
Chat or event → GoalManager → GoalPlanner → ExecutionGraph → [approve] → Executor
  → ToolRegistry → Observer → continue | block | undo
```

## API entry

`POST /api/v1/finance-os/copilot/chat`

```json
{
  "message": "Show overdue invoices and start collection workflow",
  "world_state": { "screen": { "module": "M12_AR", "entity_id": "..." } },
  "human_approved": false
}
```

## Response fields

- `goal_id`, `goal_run_id`, `status` (`plan_pending_approval`, `executing`, `completed`, `blocked`)
- `plan` — confidence, risk, reasoning, approval_points, rollback_strategy
- `graph_nodes` — DAG steps
- `observations` — per-step Observer output
- `approval_required`

## Approve and continue

`POST /api/v1/finance-os/runtime/goals/{goal_id}/runs/{run_id}/approve`

## Event path (no chat)

Same runtime via `_consume_goal_triggers` → `GoalManager.handle_event`.

## Audit

Every run: `m38.goal.run` in audit log; observations in `finance_os.runtime_observations`.
