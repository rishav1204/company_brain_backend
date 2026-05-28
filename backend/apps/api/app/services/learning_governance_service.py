from app.services.repositories import learning_governance_repo, training_eval_repo
from app.services.training_eval_service import run_eval_metrics


TRIAGE_CATEGORIES = {"retrieval", "reasoning", "policy", "data_quality"}
GOVERNANCE_APPROVER_ROLES = {"governance_admin", "tenant_admin", "cfo"}


def _triage_category(event_type: str, payload: dict) -> str:
    lowered = event_type.lower()
    if any(token in lowered for token in {"retrieval", "citation", "source"}):
        return "retrieval"
    if any(token in lowered for token in {"policy", "permission", "approval", "safety"}):
        return "policy"
    if any(token in lowered for token in {"correction", "not_helpful", "reasoning", "hallucination"}):
        return "reasoning"
    if payload.get("citation_correct") is False:
        return "retrieval"
    if payload.get("action_accepted") is False:
        return "policy"
    return "data_quality"


def triage_feedback_events(org_id: str) -> dict:
    created = 0
    for feedback in learning_governance_repo.list_untriaged_feedback(org_id=org_id):
        category = _triage_category(str(feedback.get("event_type", "")), feedback.get("payload_jsonb", {}))
        learning_governance_repo.create_labeling_task(
            org_id=org_id,
            feedback_event_id=str(feedback["id"]),
            triage_category=category,
            payload_jsonb={
                "event_type": feedback.get("event_type"),
                "payload": feedback.get("payload_jsonb", {}),
                "created_by": feedback.get("created_by"),
            },
        )
        created += 1
    return {"status": "ok", "tasks_created": created}


def approve_labeling_task(org_id: str, task_id: str, reviewer_id: str) -> dict | None:
    task = learning_governance_repo.review_labeling_task(
        org_id=org_id,
        task_id=task_id,
        reviewer_id=reviewer_id,
        status="approved",
    )
    if not task:
        return None
    payload = task.get("payload_jsonb", {})
    nested = payload.get("payload", {}) if isinstance(payload.get("payload"), dict) else {}
    if task.get("triage_category") == "retrieval" and nested.get("query") and nested.get("candidate_ref"):
        training_eval_repo.create_retrieval_judgment(
            org_id=org_id,
            query=str(nested["query"]),
            candidate_ref=str(nested["candidate_ref"]),
            relevance_label=int(nested.get("relevance_label", 2)),
            judged_by=reviewer_id,
        )
    if nested.get("question") and nested.get("expected_answer"):
        training_eval_repo.create_qa_gold_example(
            org_id=org_id,
            org_scope=str(nested.get("org_scope", "tenant")),
            question=str(nested["question"]),
            expected_answer=str(nested["expected_answer"]),
            expected_citations=nested.get("expected_citations", []),
            tags=nested.get("tags", []),
        )
    return task


def start_governance_cycle(org_id: str, candidate_version: str, created_by: str) -> dict:
    triage_feedback_events(org_id=org_id)
    return learning_governance_repo.create_cycle(
        org_id=org_id,
        candidate_version=candidate_version,
        created_by=created_by,
        status="labeling_review",
    )


def run_shadow_eval(org_id: str, cycle_id: str) -> dict:
    cycle = learning_governance_repo.get_cycle(org_id=org_id, cycle_id=cycle_id)
    if not cycle:
        return {"status": "error", "detail": "cycle_not_found"}
    baseline = learning_governance_repo.latest_eval_run(org_id=org_id, run_type="benchmark_ci")
    if baseline is None:
        baseline = learning_governance_repo.latest_eval_run(org_id=org_id, run_type="baseline")
    shadow_run = training_eval_repo.start_eval_run(org_id=org_id, run_type="shadow")
    metrics = run_eval_metrics(org_id=org_id)
    metrics["candidate_version"] = cycle.get("candidate_version")
    metrics["run_type"] = "shadow"
    completed = training_eval_repo.complete_eval_run(org_id=org_id, run_id=shadow_run["id"], metrics_jsonb=metrics)
    comparison = _compare_metrics(
        baseline_metrics=(baseline or {}).get("metrics_jsonb", {}),
        shadow_metrics=metrics,
    )
    updated = learning_governance_repo.update_cycle(
        org_id=org_id,
        cycle_id=cycle_id,
        status="promotion_review" if comparison["promotion_gate_passed"] else "rejected",
        baseline_eval_run_id=(baseline or {}).get("id"),
        shadow_eval_run_id=shadow_run["id"],
        metrics_jsonb={"shadow_eval": metrics, "comparison": comparison},
        promotion_decision="pending" if comparison["promotion_gate_passed"] else "rejected",
    )
    return {
        "status": "ok",
        "cycle": updated,
        "shadow_eval_run": completed,
        "comparison": comparison,
    }


def _compare_metrics(baseline_metrics: dict, shadow_metrics: dict) -> dict:
    keys = ("precision_at_k", "recall_at_k", "ndcg", "citation_precision", "groundedness", "hallucination_rate")
    deltas = {}
    for key in keys:
        baseline_value = float(baseline_metrics.get(key, 0.0) or 0.0)
        shadow_value = float(shadow_metrics.get(key, 0.0) or 0.0)
        deltas[key] = round(shadow_value - baseline_value, 4)
    promotion_gate_passed = bool(shadow_metrics.get("release_gate_passed")) and all(
        deltas.get(key, 0.0) >= -0.02 for key in ("precision_at_k", "recall_at_k", "ndcg", "citation_precision", "groundedness")
    ) and deltas.get("hallucination_rate", 0.0) <= 0.01
    return {
        "deltas": deltas,
        "shadow_release_gate_passed": bool(shadow_metrics.get("release_gate_passed")),
        "promotion_gate_passed": promotion_gate_passed,
    }


def approve_promotion(org_id: str, cycle_id: str, approver_id: str, roles: list[str]) -> dict:
    role_set = {role.lower() for role in roles}
    if not any(role in GOVERNANCE_APPROVER_ROLES for role in role_set):
        return {"status": "error", "detail": "governance_role_required"}
    cycle = learning_governance_repo.get_cycle(org_id=org_id, cycle_id=cycle_id)
    if not cycle:
        return {"status": "error", "detail": "cycle_not_found"}
    if cycle.get("status") != "promotion_review":
        return {"status": "error", "detail": "invalid_cycle_status"}
    comparison = (cycle.get("metrics_jsonb") or {}).get("comparison", {})
    if not comparison.get("promotion_gate_passed"):
        return {"status": "error", "detail": "promotion_gate_not_passed"}
    updated = learning_governance_repo.update_cycle(
        org_id=org_id,
        cycle_id=cycle_id,
        status="canary_rollout",
        governance_approver=approver_id,
        promotion_decision="approved",
        canary_percent=5,
        metrics_jsonb={
            **(cycle.get("metrics_jsonb") or {}),
            "governance_approval": {"approver_id": approver_id, "approved": True},
        },
    )
    return {"status": "ok", "cycle": updated}


def advance_canary(org_id: str, cycle_id: str, canary_percent: int) -> dict:
    cycle = learning_governance_repo.get_cycle(org_id=org_id, cycle_id=cycle_id)
    if not cycle or cycle.get("status") not in {"canary_rollout", "promoted"}:
        return {"status": "error", "detail": "invalid_cycle_status"}
    percent = max(0, min(canary_percent, 100))
    status = "promoted" if percent >= 100 else "canary_rollout"
    updated = learning_governance_repo.update_cycle(
        org_id=org_id,
        cycle_id=cycle_id,
        status=status,
        canary_percent=percent,
        metrics_jsonb={
            **(cycle.get("metrics_jsonb") or {}),
            "canary": {"percent": percent, "status": status},
        },
    )
    return {"status": "ok", "cycle": updated}


def rollback_cycle(org_id: str, cycle_id: str, reason: str) -> dict:
    cycle = learning_governance_repo.get_cycle(org_id=org_id, cycle_id=cycle_id)
    if not cycle:
        return {"status": "error", "detail": "cycle_not_found"}
    updated = learning_governance_repo.update_cycle(
        org_id=org_id,
        cycle_id=cycle_id,
        status="rolled_back",
        promotion_decision="rejected",
        canary_percent=0,
        metrics_jsonb={
            **(cycle.get("metrics_jsonb") or {}),
            "rollback": {"reason": reason},
        },
    )
    return {"status": "ok", "cycle": updated}
