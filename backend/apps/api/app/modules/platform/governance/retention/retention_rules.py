from __future__ import annotations

DEFAULT_RETENTION_YEARS = 8

RESOURCE_RETENTION: dict[str, int] = {
    "audit_logs": 8,
    "gst_records": 8,
    "financial_records": 8,
    "ai_traces": 3,
}


def retention_years_for(resource_type: str) -> int:
    return RESOURCE_RETENTION.get(resource_type, DEFAULT_RETENTION_YEARS)
