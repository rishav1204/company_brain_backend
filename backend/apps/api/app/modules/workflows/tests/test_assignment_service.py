from app.modules.workflows.services.assignment_service import assign_user, round_robin_assign


def test_round_robin_cycles_candidates() -> None:
    counters: dict[str, int] = {}
    a = round_robin_assign(["u1", "u2", "u3"], counter_key="role", counters=counters)
    b = round_robin_assign(["u1", "u2", "u3"], counter_key="role", counters=counters)
    c = round_robin_assign(["u1", "u2", "u3"], counter_key="role", counters=counters)
    assert (a, b, c) == ("u1", "u2", "u3")


def test_ai_assisted_prefers_suggested_assignee() -> None:
    picked = assign_user(
        strategy="ai_assisted",
        candidates=["u1", "u2"],
        workloads={"u1": 5, "u2": 1},
        counter_key="x",
        metadata={"suggested_assignee": "u1"},
    )
    assert picked == "u1"
