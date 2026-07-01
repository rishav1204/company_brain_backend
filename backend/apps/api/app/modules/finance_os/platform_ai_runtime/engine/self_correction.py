from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, ObservationResult


class SelfCorrection:
    def suggest(self, observation: ObservationResult) -> dict:
        if observation.success:
            return {"action": "continue", "auto": True}
        if observation.blocked and observation.alternatives:
            return {
                "action": "present_alternatives",
                "auto": False,
                "alternatives": observation.alternatives,
                "message": observation.reason or "blocked",
            }
        if observation.retryable:
            return {"action": "retry", "auto": True, "max_retries": 2}
        return {"action": "fail", "auto": False, "reason": observation.reason}

    def apply_alternative(self, alternatives: list[dict], index: int) -> GraphNodeSpec | None:
        if index < 0 or index >= len(alternatives):
            return None
        alt = alternatives[index]
        action = str(alt.get("action") or "")
        if not action or "." not in action:
            return None
        tool, method = action.split(".", 1)
        return GraphNodeSpec(
            id=f"alt_{index + 1}",
            tool=tool,
            method=method,
            label=str(alt.get("label") or action),
            params=dict(alt.get("params") or {}),
            requires_approval=True,
        )


self_correction = SelfCorrection()
