from app.services import learning_governance_service as governance_module


def test_triage_category_mapping() -> None:
    assert governance_module._triage_category("retrieval_miss", {}) == "retrieval"
    assert governance_module._triage_category("user_feedback", {"citation_correct": False}) == "retrieval"
    assert governance_module._triage_category("user_feedback", {"action_accepted": False}) == "policy"
    assert governance_module._triage_category("not_helpful", {}) == "reasoning"


def test_compare_metrics_passes_when_shadow_meets_gate() -> None:
    comparison = governance_module._compare_metrics(
        baseline_metrics={
            "precision_at_k": 0.96,
            "recall_at_k": 0.92,
            "ndcg": 0.91,
            "citation_precision": 0.96,
            "groundedness": 0.92,
            "hallucination_rate": 0.02,
            "release_gate_passed": True,
        },
        shadow_metrics={
            "precision_at_k": 0.97,
            "recall_at_k": 0.93,
            "ndcg": 0.92,
            "citation_precision": 0.97,
            "groundedness": 0.93,
            "hallucination_rate": 0.01,
            "release_gate_passed": True,
        },
    )
    assert comparison["promotion_gate_passed"] is True


def test_compare_metrics_fails_when_shadow_regresses() -> None:
    comparison = governance_module._compare_metrics(
        baseline_metrics={
            "precision_at_k": 0.96,
            "recall_at_k": 0.92,
            "ndcg": 0.91,
            "citation_precision": 0.96,
            "groundedness": 0.92,
            "hallucination_rate": 0.02,
            "release_gate_passed": True,
        },
        shadow_metrics={
            "precision_at_k": 0.90,
            "recall_at_k": 0.80,
            "ndcg": 0.75,
            "citation_precision": 0.90,
            "groundedness": 0.80,
            "hallucination_rate": 0.08,
            "release_gate_passed": False,
        },
    )
    assert comparison["promotion_gate_passed"] is False


def test_governance_loop_end_to_end(monkeypatch) -> None:
    store = {
        "feedback": [{"id": "fb-1", "event_type": "not_helpful", "payload_jsonb": {"query": "q1"}, "created_by": "u1"}],
        "tasks": [],
        "cycles": [],
        "eval_runs": [],
    }

    monkeypatch.setattr(
        governance_module.learning_governance_repo,
        "list_untriaged_feedback",
        lambda org_id, limit=200: list(store["feedback"]),
    )
    monkeypatch.setattr(
        governance_module.learning_governance_repo,
        "list_feedback_events",
        lambda org_id, limit=200: list(store["feedback"]),
    )

    def _create_task(**kwargs):
        task = {"id": "task-1", "status": "pending_review", **kwargs}
        store["tasks"].append(task)
        return task

    monkeypatch.setattr(governance_module.learning_governance_repo, "create_labeling_task", _create_task)

    def _create_cycle(**kwargs):
        cycle = {
            "id": "cycle-1",
            "promotion_decision": "pending",
            "canary_percent": 0,
            "metrics_jsonb": {},
            **kwargs,
        }
        store["cycles"].append(cycle)
        return cycle

    monkeypatch.setattr(governance_module.learning_governance_repo, "create_cycle", _create_cycle)
    monkeypatch.setattr(
        governance_module.learning_governance_repo,
        "get_cycle",
        lambda org_id, cycle_id: next((c for c in store["cycles"] if c["id"] == cycle_id), None),
    )
    monkeypatch.setattr(
        governance_module.learning_governance_repo,
        "latest_eval_run",
        lambda org_id, run_type: {
            "id": "baseline-1",
            "metrics_jsonb": {
                "precision_at_k": 0.96,
                "recall_at_k": 0.92,
                "ndcg": 0.91,
                "citation_precision": 0.96,
                "groundedness": 0.92,
                "hallucination_rate": 0.02,
                "release_gate_passed": True,
            },
        },
    )
    monkeypatch.setattr(
        governance_module.training_eval_repo,
        "start_eval_run",
        lambda org_id, run_type: {"id": "shadow-1", "run_type": run_type},
    )
    monkeypatch.setattr(
        governance_module,
        "run_eval_metrics",
        lambda org_id: {
            "precision_at_k": 0.97,
            "recall_at_k": 0.93,
            "ndcg": 0.92,
            "citation_precision": 0.97,
            "groundedness": 0.93,
            "hallucination_rate": 0.01,
            "release_gate_passed": True,
        },
    )
    monkeypatch.setattr(
        governance_module.training_eval_repo,
        "complete_eval_run",
        lambda org_id, run_id, metrics_jsonb, status="completed": {"id": run_id, "metrics_jsonb": metrics_jsonb},
    )

    def _update_cycle(org_id, cycle_id, **kwargs):
        cycle = next(c for c in store["cycles"] if c["id"] == cycle_id)
        cycle.update(kwargs)
        return cycle

    monkeypatch.setattr(governance_module.learning_governance_repo, "update_cycle", _update_cycle)

    triage = governance_module.triage_feedback_events("org-demo")
    assert triage["tasks_created"] == 1

    cycle = governance_module.start_governance_cycle("org-demo", "v2026.05.2", "admin-1")
    assert cycle["status"] == "labeling_review"

    shadow = governance_module.run_shadow_eval("org-demo", "cycle-1")
    assert shadow["status"] == "ok"
    assert shadow["comparison"]["promotion_gate_passed"] is True
    assert store["cycles"][0]["status"] == "promotion_review"

    denied = governance_module.approve_promotion("org-demo", "cycle-1", "user-1", ["analyst"])
    assert denied["status"] == "error"

    approved = governance_module.approve_promotion("org-demo", "cycle-1", "gov-1", ["governance_admin"])
    assert approved["status"] == "ok"
    assert store["cycles"][0]["status"] == "canary_rollout"

    canary = governance_module.advance_canary("org-demo", "cycle-1", 100)
    assert canary["status"] == "ok"
    assert store["cycles"][0]["status"] == "promoted"
