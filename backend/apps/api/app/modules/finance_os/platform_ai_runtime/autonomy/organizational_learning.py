"""Organizational learning — operational patterns only; never policy exceptions (Wave 5)."""

from __future__ import annotations

from collections import Counter

from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.services.logger import log_event

# Patterns learned are stored on goal.plan_metadata["learning"] or run metadata — not a new DB.


class OrganizationalLearning:
    """Improve planning efficiency from approval timing, bottlenecks, rejections.

    Explicitly does NOT learn policy overrides or RBAC exceptions.
    """

    FORBIDDEN_TOPICS = (
        "bypass",
        "policy_exception",
        "skip_approval",
        "human_approved_override",
        "role_escalation",
    )

    def observe_run(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        observations: list[dict],
        plan_meta: dict | None = None,
    ) -> dict:
        outcomes = Counter()
        tools = Counter()
        retries = 0
        blocked = 0
        for obs in observations:
            status = str(obs.get("status") or obs.get("outcome") or "")
            outcomes[status] += 1
            tools[f"{obs.get('tool_name') or obs.get('tool')}.{obs.get('tool_method') or obs.get('method')}"] += 1
            if status in {"needs_retry", "failed"} and obs.get("retryable"):
                retries += 1
            if status in {"blocked", "needs_human", "needs_escalation"}:
                blocked += 1
        # Reject anything that smells like policy learning
        summary = {
            "outcome_counts": dict(outcomes),
            "tool_frequency": dict(tools.most_common(10)),
            "retries": retries,
            "blocked_count": blocked,
            "preferred_sequences": self._sequence_hint(observations),
            "bottleneck_tools": [t for t, _ in tools.most_common(3) if t and t != "."],
        }
        text = str(summary).lower()
        if any(f in text for f in self.FORBIDDEN_TOPICS):
            log_event("m38.learning.blocked_policy_content", org_id=org_id, goal_id=goal_id)
            return {"status": "blocked", "reason": "policy_content_rejected"}

        try:
            goal_repository.merge_plan_metadata(
                org_id,
                goal_id,
                {"learning": summary, "learning_source_run": run_id},
            )
        except Exception as exc:
            log_event("m38.learning.persist_failed", org_id=org_id, detail=str(exc))
        return {"status": "ok", "patterns": summary}

    def _sequence_hint(self, observations: list[dict]) -> list[str]:
        seq = []
        for obs in observations:
            if str(obs.get("status")) in {"success", "partial_success"}:
                t = f"{obs.get('tool_name') or obs.get('tool')}.{obs.get('tool_method') or obs.get('method')}"
                if t and t != ".":
                    seq.append(t)
        return seq[:12]

    def planning_hints(self, org_id: str, goal_id: str | None = None) -> list[str]:
        """Hints for planner/optimizer only — never authorization."""
        hints: list[str] = []
        if goal_id:
            goal = goal_repository.get_goal(org_id, goal_id)
            if goal:
                meta = goal.get("plan_metadata") or {}
                learning = meta.get("learning") if isinstance(meta, dict) else None
                if isinstance(learning, dict):
                    if learning.get("bottleneck_tools"):
                        hints.append(f"historical_bottlenecks={learning['bottleneck_tools'][:3]}")
                    if learning.get("preferred_sequences"):
                        hints.append(f"preferred_sequence={learning['preferred_sequences'][:5]}")
                    if learning.get("blocked_count", 0) > 2:
                        hints.append("batch_approval_prep=true")
        return hints


organizational_learning = OrganizationalLearning()
