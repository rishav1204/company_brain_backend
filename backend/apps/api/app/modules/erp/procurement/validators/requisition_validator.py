from __future__ import annotations

PR_EDITABLE = {"draft"}
PR_SUBMITTABLE = {"draft"}
PR_APPROVABLE = {"submitted"}
PR_CONVERTIBLE = {"approved"}
PR_CANCELLABLE = {"draft", "submitted"}


def ensure_editable(status: str) -> None:
    if status not in PR_EDITABLE:
        raise ValueError(f"PR cannot be edited in status {status}")


def ensure_submittable(status: str) -> None:
    if status not in PR_SUBMITTABLE:
        raise ValueError(f"PR cannot be submitted from status {status}")


def ensure_approvable(status: str) -> None:
    if status not in PR_APPROVABLE:
        raise ValueError(f"PR cannot be approved from status {status}")


def ensure_convertible(status: str) -> None:
    if status not in PR_CONVERTIBLE:
        raise ValueError(f"PR cannot be converted from status {status}")


def ensure_cancellable(status: str) -> None:
    if status not in PR_CANCELLABLE:
        raise ValueError(f"PR cannot be cancelled from status {status}")
