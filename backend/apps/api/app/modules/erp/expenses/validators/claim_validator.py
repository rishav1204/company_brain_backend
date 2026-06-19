from __future__ import annotations

SUBMITTABLE = {"draft"}
APPROVABLE = {"submitted", "under_review"}
CANCELLABLE = {"draft", "submitted"}


def ensure_editable(status: str) -> None:
    if status not in {"draft"}:
        raise ValueError(f"Claim cannot be edited in status {status}")


def ensure_submittable(status: str) -> None:
    if status not in SUBMITTABLE:
        raise ValueError(f"Claim cannot be submitted from status {status}")


def ensure_approvable(status: str) -> None:
    if status not in APPROVABLE:
        raise ValueError(f"Claim cannot be approved from status {status}")


def ensure_cancellable(status: str) -> None:
    if status not in CANCELLABLE:
        raise ValueError(f"Claim cannot be cancelled from status {status}")
