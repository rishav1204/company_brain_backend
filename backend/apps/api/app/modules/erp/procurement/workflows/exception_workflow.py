from __future__ import annotations


def exception_workflow_metadata(*, match_id: str, po_id: str, variance: dict) -> dict:
    return {"match_id": match_id, "po_id": po_id, "variance": variance}
