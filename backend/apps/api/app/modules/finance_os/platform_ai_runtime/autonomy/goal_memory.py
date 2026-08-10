"""Goal Memory — operational/financial objectives beyond a single chat (Wave 5)."""

from __future__ import annotations

from uuid import uuid4

from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GoalObjective, WorldState
from app.services.logger import log_event


class GoalMemory:
    """Session-surviving objectives on goals.world_state + durable M27 outcome notes."""

    def load_from_world_state(self, world_state: WorldState | None) -> list[GoalObjective]:
        if not world_state:
            return []
        out: list[GoalObjective] = []
        for raw in world_state.operational_objectives or []:
            if not isinstance(raw, dict):
                continue
            try:
                if not raw.get("objective_id"):
                    raw = {**raw, "objective_id": str(uuid4())}
                out.append(GoalObjective(**raw))
            except Exception:
                continue
        return out

    def load_active_objectives(self, org_id: str, *, limit: int = 20) -> list[GoalObjective]:
        goals = goal_repository.list_goals(org_id, status="active", limit=limit)
        collected: list[GoalObjective] = []
        for g in goals:
            full = goal_repository.get_goal(org_id, g["id"])
            if not full:
                continue
            ws = full.get("world_state") or {}
            if not isinstance(ws, dict):
                continue
            for raw in ws.get("operational_objectives") or []:
                if isinstance(raw, dict) and raw.get("status", "active") == "active":
                    try:
                        obj = GoalObjective(**{**raw, "objective_id": raw.get("objective_id") or str(uuid4())})
                        if g["id"] not in obj.linked_goal_ids:
                            obj.linked_goal_ids = list(obj.linked_goal_ids) + [g["id"]]
                        collected.append(obj)
                    except Exception:
                        continue
        return collected[:limit]

    def attach_objectives(
        self,
        world_state: WorldState | None,
        objectives: list[GoalObjective],
        *,
        financial_targets: dict | None = None,
    ) -> WorldState:
        ws = world_state or WorldState()
        existing = list(ws.operational_objectives or [])
        for obj in objectives:
            existing.append(obj.model_dump())
        data = ws.model_dump()
        data["operational_objectives"] = existing[-50:]
        if financial_targets:
            data["financial_targets"] = {**(data.get("financial_targets") or {}), **financial_targets}
        return WorldState(**data)

    def summarize_for_planner(self, org_id: str) -> list[str]:
        objs = self.load_active_objectives(org_id, limit=12)
        return [f"{o.kind}:{o.metric or 'n/a'}:{o.title}" for o in objs]

    def remember_outcome(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        summary: str,
        objectives: list[str] | None = None,
    ) -> None:
        """Durable operational outcome — never stores policy exceptions."""
        content = summary[:800]
        if objectives:
            content = f"Objectives: {', '.join(objectives[:5])}. {content}"[:800]
        try:
            from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service

            memory_writer_service.write(
                org_id,
                memory_type="operational",
                entity_type="goal",
                entity_id=goal_id,
                title="Goal outcome",
                content=content,
                importance_score=70.0,
                source_event_type="m38.goal.completed",
                force=False,
            )
        except Exception as exc:
            # Fallback to agent path if operational type unavailable
            try:
                from app.modules.finance_os.agents.services.agent_memory_service import write_outcome

                write_outcome(org_id, "platform_ai_runtime", run_id, content if len(content) >= 20 else content + " [goal outcome]")
            except Exception as exc2:
                log_event("m38.goal_memory.write_failed", org_id=org_id, detail=str(exc2 or exc))

    def find_matching_goal(
        self,
        org_id: str,
        *,
        title_hint: str | None = None,
        template_key: str | None = None,
        entity_id: str | None = None,
    ) -> dict | None:
        """Prefer resuming existing operational goal over opening a duplicate."""
        goals = goal_repository.list_goals_detailed(org_id, status="active", limit=30)
        for g in goals:
            trigger = g.get("trigger_config") or {}
            if not isinstance(trigger, dict):
                trigger = {}
            if template_key and trigger.get("template_key") == template_key:
                return g
            if entity_id:
                ws = g.get("world_state") or {}
                if isinstance(ws, dict):
                    sel = ws.get("selection") or {}
                    if entity_id in {
                        ws.get("current_invoice_id"),
                        (ws.get("screen") or {}).get("entity_id") if isinstance(ws.get("screen"), dict) else None,
                        sel.get("invoice_id"),
                        sel.get("entity_id"),
                    }:
                        return g
            if title_hint and (g.get("title") or "")[:80] == title_hint[:80]:
                return g
        return None


goal_memory = GoalMemory()
