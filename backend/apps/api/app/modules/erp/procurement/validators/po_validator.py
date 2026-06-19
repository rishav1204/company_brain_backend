from __future__ import annotations

PO_EDITABLE = {"draft"}
PO_SUBMITTABLE = {"draft"}
PO_SENDABLE = {"approved"}
PO_CANCELLABLE = {"draft", "pending_approval"}
PO_RECEIVABLE = {"sent", "partially_received", "received"}


def ensure_editable(status: str) -> None:
    if status not in PO_EDITABLE:
        raise ValueError(f"PO cannot be edited in status {status}")


def ensure_submittable(status: str) -> None:
    if status not in PO_SUBMITTABLE:
        raise ValueError(f"PO cannot be submitted from status {status}")


def ensure_sendable(status: str) -> None:
    if status not in PO_SENDABLE:
        raise ValueError(f"PO cannot be sent from status {status}")


def ensure_cancellable(status: str) -> None:
    if status not in PO_CANCELLABLE:
        raise ValueError(f"PO cannot be cancelled from status {status}")


def ensure_receivable(status: str) -> None:
    if status not in PO_RECEIVABLE:
        raise ValueError(f"GRN cannot be created for PO in status {status}")
