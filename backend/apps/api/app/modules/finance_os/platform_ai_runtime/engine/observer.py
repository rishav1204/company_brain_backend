from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec, ObservationResult, WorldState


class Observer:
    """Observer V2 — continuous outcome evaluation; never premature goal termination (Wave 5)."""

    def analyze(
        self,
        node: GraphNodeSpec,
        result: dict,
        *,
        world_state: WorldState | None = None,
    ) -> ObservationResult:
        status = str(result.get("status") or "error").lower()
        detail = str(result.get("detail") or result.get("message") or result.get("reason") or "")
        code = str(result.get("code") or "").upper()
        success = status in {"completed", "success", "ok"}
        retryable = False
        blocked = False
        alternatives: list[dict] = []
        reason: str | None = None
        facts: dict = {}
        outcome = "unknown"
        escalate = False
        partial = False
        # Wave 5: never set terminate_goal for recoverable partial/blocked — goals resume
        terminate_goal = False

        if success:
            # Partial success when tool reports incomplete coverage
            if result.get("partial") or result.get("partial_success") or status == "partial":
                partial = True
                outcome = "partial_success"
                return ObservationResult(
                    node_id=node.id,
                    tool=node.tool,
                    method=node.method,
                    status="partial_success",
                    success=True,
                    partial=True,
                    outcome=outcome,
                    terminate_goal=False,
                    reason="partial_success",
                    facts=result.get("facts") or {},
                    raw_result=result,
                )
            return ObservationResult(
                node_id=node.id,
                tool=node.tool,
                method=node.method,
                status="success",
                success=True,
                outcome="succeeded",
                terminate_goal=False,
                raw_result=result,
            )

        # Prep-only / autonomy mutation gate — human path, keep goal alive
        if code in {"PREP_ONLY_MUTATION", "AUTONOMY_MUTATION_BLOCKED"} or status == "pending_approval":
            return ObservationResult(
                node_id=node.id,
                tool=node.tool,
                method=node.method,
                status="needs_human",
                success=False,
                blocked=True,
                outcome="needs_human",
                reason="awaiting_human_approval",
                terminate_goal=False,
                alternatives=[{"action": "approve_continue", "label": "Approve and continue"}],
                raw_result=result,
            )

        if (
            "insufficient" in detail.lower()
            or "insufficient_cash" in detail.lower()
            or (status == "blocked" and "cash" in detail.lower())
        ):
            blocked = True
            reason = "insufficient_cash"
            outcome = "needs_alternative"
            facts = result.get("facts") or {"detail": detail}
            alternatives = [
                {"action": "payment.postpone", "label": "Postpone payment 7 days"},
                {"action": "payment.split", "label": "Split into 2 tranches"},
                {"action": "treasury.transfer_request", "label": "Request inter-account transfer"},
                {"action": "notification.send", "label": "Notify finance manager"},
            ]
        elif "policy" in detail.lower() or detail == "abac_denied" or code == "ABAC_DENIED":
            blocked = True
            reason = "policy_denied"
            outcome = "needs_human"
            alternatives = [{"action": "workflow.start", "label": "Start approval workflow"}]
        elif "forbidden" in detail.lower() or code.startswith("FORBIDDEN"):
            blocked = True
            reason = "forbidden_action"
            outcome = "needs_escalation"
            escalate = True
        elif status in {"partial", "partial_success"} or result.get("partial"):
            partial = True
            success = True  # do not fail goal
            outcome = "partial_success"
            reason = detail or "partial_success"
        elif status == "error" and (result.get("retryable") is True or "timeout" in detail.lower() or "temporary" in detail.lower()):
            retryable = True
            outcome = "needs_retry"
            reason = detail or "execution_failed"
            alternatives = [{"action": "retry", "label": "Retry this step"}]
        elif status == "error":
            retryable = bool(result.get("retryable"))
            outcome = "needs_retry" if retryable else "failed"
            reason = detail or "execution_failed"
            alternatives = [{"action": "retry", "label": "Retry this step"}]
            if "rollback" in detail.lower() or result.get("needs_rollback"):
                outcome = "needs_rollback"
        elif status == "blocked":
            blocked = True
            outcome = "needs_alternative"
            reason = detail or "blocked"
            alternatives = result.get("alternatives") if isinstance(result.get("alternatives"), list) else []
        else:
            outcome = "failed"
            reason = detail or status
            retryable = bool(result.get("retryable"))

        # Escalation marker for repeated blocks (caller can count)
        if blocked and result.get("escalation_count", 0) >= 2:
            escalate = True
            outcome = "needs_escalation"

        display_status = "blocked" if blocked else ("failed" if outcome == "failed" else outcome)

        return ObservationResult(
            node_id=node.id,
            tool=node.tool,
            method=node.method,
            status=display_status,
            success=success,
            retryable=retryable,
            blocked=blocked,
            reason=reason,
            facts=facts,
            alternatives=alternatives,
            raw_result=result,
            outcome=outcome,
            escalate=escalate,
            partial=partial,
            terminate_goal=terminate_goal,
        )


observer = Observer()
