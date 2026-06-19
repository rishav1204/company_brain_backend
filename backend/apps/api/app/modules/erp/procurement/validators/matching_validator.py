from __future__ import annotations

MATCH_APPROVABLE = {"matched", "matched_within_tolerance"}
MATCH_OVERRIDABLE = {"exception", "rejected"}


def ensure_invoice_approvable(match_status: str | None) -> None:
    if match_status is None:
        return
    if match_status not in MATCH_APPROVABLE:
        raise ValueError(f"Three-way match status '{match_status}' blocks invoice approval")


def ensure_overridable(match_status: str) -> None:
    if match_status not in MATCH_OVERRIDABLE:
        raise ValueError(f"Match cannot be overridden from status {match_status}")
