from __future__ import annotations

SUBMITTABLE = {"draft"}


def ensure_submittable(status: str) -> None:
    if status not in SUBMITTABLE:
        raise ValueError(f"Asset cannot be submitted from status {status}")
