from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import ConversationState, ResolvedEntity
from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository


class WorkingMemoryManager:
    def load(self, org_id: str, goal_id: str | None) -> ConversationState:
        if not goal_id:
            return ConversationState()
        goal = goal_repository.get_goal(org_id, goal_id)
        if not goal:
            return ConversationState()
        raw = goal.get("conversation_state") or {}
        if isinstance(raw, dict):
            try:
                return ConversationState(**raw)
            except Exception:
                return ConversationState()
        return ConversationState()

    def save(
        self,
        org_id: str,
        goal_id: str,
        *,
        state: ConversationState,
        entities: list[ResolvedEntity] | None = None,
        intent: str | None = None,
    ) -> ConversationState:
        updated = state.model_copy()
        updated.turn_count = (updated.turn_count or 0) + 1
        if intent:
            updated.last_intent = intent
        if entities:
            for e in entities:
                if e.entity_type == "vendor" and e.entity_id:
                    updated.current_vendor_id = e.entity_id
                if e.entity_type == "period" and (e.entity_id or e.label):
                    updated.current_period = e.entity_id or e.label
                if e.entity_id and e.entity_type not in {"period"}:
                    updated.current_entity = {"type": e.entity_type, "id": e.entity_id}
                if e.entity_type not in updated.topic_stack:
                    updated.topic_stack = (updated.topic_stack + [e.entity_type])[-8:]
        goal_repository.update_conversation_state(org_id, goal_id, updated.model_dump())
        return updated


working_memory = WorkingMemoryManager()
