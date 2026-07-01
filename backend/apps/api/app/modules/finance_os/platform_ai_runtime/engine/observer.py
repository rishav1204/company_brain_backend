from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, ObservationResult, WorldState


class Observer:
    def analyze(
        self,
        node: GraphNodeSpec,
        result: dict,
        *,
        world_state: WorldState | None = None,
    ) -> ObservationResult:
        status = str(result.get("status") or "error").lower()
        detail = str(result.get("detail") or result.get("message") or result.get("reason") or "")
        success = status == "completed"
        retryable = status == "error" and result.get("retryable") is True
        blocked = False
        alternatives: list[dict] = []
        reason: str | None = None
        facts: dict = {}

        if success:
            return ObservationResult(
                node_id=node.id,
                tool=node.tool,
                method=node.method,
                status="success",
                success=True,
                raw_result=result,
            )

        if "insufficient" in detail.lower() or "insufficient_cash" in detail.lower() or status == "blocked" and "cash" in detail.lower():
            blocked = True
            reason = "insufficient_cash"
            facts = result.get("facts") or {"detail": detail}
            alternatives = [
                {"action": "payment.postpone", "label": "Postpone payment 7 days"},
                {"action": "payment.split", "label": "Split into 2 tranches"},
                {"action": "treasury.transfer_request", "label": "Request inter-account transfer"},
                {"action": "notification.send", "label": "Notify finance manager"},
            ]
        elif "policy" in detail.lower() or detail == "abac_denied":
            blocked = True
            reason = "policy_denied"
            alternatives = [{"action": "workflow.start", "label": "Start approval workflow"}]
        elif "forbidden" in detail.lower():
            blocked = True
            reason = "forbidden_action"
        elif status == "error":
            retryable = True
            reason = detail or "execution_failed"
            alternatives = [{"action": "retry", "label": "Retry this step"}]

        return ObservationResult(
            node_id=node.id,
            tool=node.tool,
            method=node.method,
            status="blocked" if blocked else "failed",
            success=False,
            retryable=retryable,
            blocked=blocked,
            reason=reason,
            facts=facts,
            alternatives=alternatives,
            raw_result=result,
        )


observer = Observer()
