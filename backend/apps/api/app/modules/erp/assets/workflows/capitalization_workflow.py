from __future__ import annotations


def workflow_metadata(*, asset_id: str, amount: float) -> dict:
    return {"asset_id": asset_id, "amount": amount}
