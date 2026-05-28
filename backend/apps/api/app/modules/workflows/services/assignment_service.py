from __future__ import annotations

from collections import defaultdict
from typing import Any


_assignment_counters: dict[str, int] = defaultdict(int)


def round_robin_assign(candidates: list[str], *, counter_key: str, counters: dict[str, int] | None = None) -> str | None:
    if not candidates:
        return None
    store = counters if counters is not None else _assignment_counters
    idx = store.get(counter_key, 0) % len(candidates)
    store[counter_key] = idx + 1
    return candidates[idx]


def lowest_workload_assign(candidates: list[str], workloads: dict[str, int]) -> str | None:
    if not candidates:
        return None
    return min(candidates, key=lambda uid: workloads.get(uid, 0))


def ai_assisted_assign(
    candidates: list[str],
    *,
    metadata: dict | None,
    workloads: dict[str, int],
) -> str | None:
    if not candidates:
        return None
    meta = metadata or {}
    suggested = meta.get("suggested_assignee") or meta.get("ai_suggested_assignee")
    if suggested and str(suggested) in candidates:
        return str(suggested)
    preferred_role_score = meta.get("assignment_scores")
    if isinstance(preferred_role_score, dict):
        scored = [(uid, float(preferred_role_score.get(uid, 0))) for uid in candidates if uid in preferred_role_score]
        if scored:
            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[0][0]
    return lowest_workload_assign(candidates, workloads)


def assign_user(
    *,
    strategy: str,
    candidates: list[str],
    workloads: dict[str, int],
    counter_key: str,
    metadata: dict | None = None,
) -> str | None:
    normalized = (strategy or "load_balance").strip().lower()
    if normalized in {"round_robin", "round-robin"}:
        return round_robin_assign(candidates, counter_key=counter_key)
    if normalized in {"ai", "ai_assisted", "ai-assisted"}:
        return ai_assisted_assign(candidates, metadata=metadata, workloads=workloads)
    return lowest_workload_assign(candidates, workloads)


def build_workload_map(assignments: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in assignments:
        uid = row.get("assigned_to") or row.get("owner_user_id")
        if uid:
            counts[str(uid)] += 1
    return dict(counts)
