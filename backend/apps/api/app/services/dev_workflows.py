from datetime import datetime, timezone

from app.core.config import settings
from app.modules.core.iam.services.identity_resolver import DEV_USER_UUID

DEV_ORG_ID = "11111111-1111-4111-8111-111111111111"
DEV_BRANCH_ID = "d0000001-0001-4001-8001-000000000001"
DEV_COMPANY_ID = "c0000001-0001-4001-8001-000000000001"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sample_rows(org_id: str) -> list[dict]:
    started = _now()
    return [
        {
            "id": "33333333-3333-4333-8333-333333333331",
            "org_id": org_id,
            "workflow_type": "ap_invoice",
            "state": "pending",
            "owner_user_id": DEV_USER_UUID,
            "started_at": started,
            "closed_at": None,
            "reference_number": "INV-AP-1001",
            "amount": 12500.0,
            "metadata": {
                "branch_id": DEV_BRANCH_ID,
                "company_id": DEV_COMPANY_ID,
                "vendor_name": "Acme Supplies",
                "confidence": 0.91,
                "verification_status": "policy_checked",
                "ai_suggestion": "Verify PO match before approval",
            },
        },
        {
            "id": "33333333-3333-4333-8333-333333333332",
            "org_id": org_id,
            "workflow_type": "ap_invoice",
            "state": "pending_approval",
            "owner_user_id": DEV_USER_UUID,
            "started_at": started,
            "closed_at": None,
            "reference_number": "INV-AP-1002",
            "amount": 48200.0,
            "metadata": {
                "vendor_name": "Global Parts Ltd",
                "confidence": 0.88,
                "verification_status": "human_approval_required",
                "ai_suggestion": "Amount exceeds threshold — controller review required",
            },
        },
        {
            "id": "44444444-4444-4444-8444-444444444441",
            "org_id": org_id,
            "workflow_type": "ar_invoice",
            "state": "pending",
            "owner_user_id": DEV_USER_UUID,
            "started_at": started,
            "closed_at": None,
            "reference_number": "INV-AR-2001",
            "amount": 8900.0,
            "metadata": {
                "customer_name": "Northwind Trading",
                "confidence": 0.93,
                "verification_status": "verified",
            },
        },
        {
            "id": "55555555-5555-4555-8555-555555555551",
            "org_id": org_id,
            "workflow_type": "close_orchestration",
            "state": "blocked",
            "owner_user_id": DEV_USER_UUID,
            "started_at": started,
            "closed_at": None,
            "reference_number": "CLOSE-2026-05",
            "amount": 0.0,
            "metadata": {
                "confidence": 0.86,
                "verification_status": "close_blocker_detected",
            },
        },
    ]


def list_dev_workflows(
    org_id: str,
    workflow_type: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict]:
    rows = _sample_rows(org_id)
    if workflow_type:
        rows = [row for row in rows if row["workflow_type"] == workflow_type]
    if status:
        normalized = status.strip().lower()
        if normalized == "pending":
            rows = [row for row in rows if row["state"] in {"pending", "pending_approval"}]
        else:
            rows = [row for row in rows if row["state"] == normalized]
    return rows[:limit]


def postgres_configured() -> bool:
    return bool(settings.postgres_dsn.strip())


def dev_workflow_state_counts(org_id: str) -> dict:
    rows = _sample_rows(org_id)
    return {
        "total": len(rows),
        "blocked_count": sum(1 for row in rows if row["state"] == "blocked"),
        "pending_approval_count": sum(1 for row in rows if row["state"] == "pending_approval"),
    }
