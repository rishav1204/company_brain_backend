from __future__ import annotations

from datetime import datetime
from typing import Any


def build_execution_graph(
    *,
    definition_steps: list[dict[str, Any]],
    executed_steps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exec_by_key = {str(s.get("step_key")): s for s in executed_steps}
    graph: list[dict[str, Any]] = []
    for step_def in definition_steps:
        key = str(step_def.get("key") or step_def.get("step_key") or "")
        executed = exec_by_key.get(key, {})
        entered = executed.get("started_at")
        exited = executed.get("completed_at")
        duration = 0
        if entered and exited:
            try:
                t0 = datetime.fromisoformat(str(entered).replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(str(exited).replace("Z", "+00:00"))
                duration = max(0, int((t1 - t0).total_seconds()))
            except ValueError:
                duration = 0
        graph.append(
            {
                "step_key": key,
                "stage_name": step_def.get("name") or key,
                "step_type": executed.get("step_type") or step_def.get("type"),
                "status": executed.get("status") or "pending",
                "assignee_id": executed.get("assigned_to"),
                "duration_seconds": duration,
                "entered_at": entered,
                "exited_at": exited,
            }
        )
    for ex in executed_steps:
        key = str(ex.get("step_key") or "")
        if key and key not in exec_by_key:
            continue
        if key and not any(g["step_key"] == key for g in graph):
            graph.append(
                {
                    "step_key": key,
                    "stage_name": key,
                    "step_type": ex.get("step_type"),
                    "status": ex.get("status"),
                    "assignee_id": ex.get("assigned_to"),
                    "duration_seconds": 0,
                }
            )
    return graph


def remaining_stages(graph: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [n for n in graph if str(n.get("status")) not in {"completed", "skipped", "cancelled"}]
