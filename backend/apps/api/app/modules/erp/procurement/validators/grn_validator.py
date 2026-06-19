from __future__ import annotations

GRN_CONFIRMABLE = {"draft"}


def ensure_confirmable(status: str) -> None:
    if status not in GRN_CONFIRMABLE:
        raise ValueError(f"GRN cannot be confirmed from status {status}")


def validate_received_qty(*, ordered: float, already_received: float, incoming: float) -> None:
    remaining = ordered - already_received
    if incoming <= 0:
        raise ValueError("Received quantity must be positive")
    if incoming > remaining + 0.0001:
        raise ValueError(f"Received quantity {incoming} exceeds remaining {remaining}")
