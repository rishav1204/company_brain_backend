from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import ConversationState, ResolvedEntity
from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository


_MAX_REASONING = 12
_MAX_TOPICS = 8
_MAX_COMPARISONS = 6


class WorkingMemoryManager:
    """Short-term operational memory — session/goal scoped (Wave 4)."""

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
        user_message: str | None = None,
        assistant_summary: str | None = None,
        task: str | None = None,
        reasoning_step: str | None = None,
    ) -> ConversationState:
        updated = state.model_copy()
        updated.turn_count = (updated.turn_count or 0) + 1
        if intent:
            updated.last_intent = intent
        if user_message:
            updated.last_user_utterance = user_message[:500]
            # Infer current task from phrasing when not set
            if not updated.current_task or intent in {"action", "workflow"}:
                updated.current_task = user_message[:200]
        if assistant_summary:
            updated.last_assistant_summary = assistant_summary[:400]
        if task:
            updated.current_task = task[:200]
        if reasoning_step:
            chain = list(updated.reasoning_chain or [])
            chain.append(reasoning_step[:300])
            updated.reasoning_chain = chain[-_MAX_REASONING:]
        if entities:
            for e in entities:
                if e.entity_type == "vendor" and e.entity_id:
                    updated.current_vendor_id = e.entity_id
                if e.entity_type == "customer" and e.entity_id:
                    updated.current_customer_id = e.entity_id
                if e.entity_type == "period" and (e.entity_id or e.label):
                    updated.current_period = e.entity_id or e.label
                if e.entity_id and e.entity_type not in {"period"}:
                    updated.current_entity = {
                        "type": e.entity_type,
                        "id": e.entity_id,
                        "label": e.label,
                    }
                topic = e.entity_type
                if topic and topic not in updated.topic_stack:
                    updated.topic_stack = (updated.topic_stack + [topic])[-_MAX_TOPICS:]
        # Forget noise: drop oldest comparison slots if topics no longer overlap
        if updated.current_comparisons and updated.topic_stack:
            updated.current_comparisons = [
                c for c in updated.current_comparisons if any(t in c.lower() for t in updated.topic_stack)
            ][-_MAX_COMPARISONS:]
        goal_repository.update_conversation_state(org_id, goal_id, updated.model_dump())
        return updated

    def note_comparison(self, state: ConversationState, label: str) -> ConversationState:
        upd = state.model_copy()
        comps = list(upd.current_comparisons or [])
        comps.append(label[:120])
        upd.current_comparisons = comps[-_MAX_COMPARISONS:]
        return upd

    def note_report(self, state: ConversationState, report_key: str) -> ConversationState:
        upd = state.model_copy()
        reports = list(upd.current_reports or [])
        if report_key not in reports:
            reports.append(report_key)
        upd.current_reports = reports[-8:]
        return upd


working_memory = WorkingMemoryManager()
