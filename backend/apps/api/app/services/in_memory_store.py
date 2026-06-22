from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import DEV_ORG_ID


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryStore:
    def __init__(self) -> None:
        self.sources: dict[str, dict] = {}
        self.ingestion_runs: dict[str, dict] = {}
        self.invoices: dict[str, dict] = {
            "inv-1001": {
                "id": "inv-1001",
                "org_id": DEV_ORG_ID,
                "invoice_number": "INV-1001",
                "vendor": "Acme Corp",
                "vendor_id": "vend-1",
                "po_id": "po-1",
                "amount": 5000.0,
                "due_date": "2026-06-30",
                "status": "Pending",
            }
        }
        self.payments: dict[str, dict] = {
            "pay-1001": {
                "id": "pay-1001",
                "org_id": DEV_ORG_ID,
                "invoice_id": "inv-1001",
                "amount": 5000.0,
                "status": "Pending",
            }
        }
        self.workflows: dict[str, dict] = {
            "wf-close-1": {
                "id": "wf-close-1",
                "org_id": DEV_ORG_ID,
                "workflow_type": "close",
                "state": "blocked",
                "owner_user_id": "user-cfo-1",
                "started_at": _now(),
                "closed_at": None,
            },
            "wf-ap-1": {
                "id": "wf-ap-1",
                "org_id": DEV_ORG_ID,
                "workflow_type": "ap_exception",
                "state": "pending_approval",
                "owner_user_id": "user-ap-1",
                "started_at": _now(),
                "closed_at": None,
            },
        }
        self.workflow_timeline: dict[str, list[dict]] = {
            "wf-close-1": [
                {"event_type": "workflow.started", "occurred_at": _now(), "detail": "Month-end close opened"},
                {"event_type": "workflow.blocker.detected", "occurred_at": _now(), "detail": "Intercompany mismatch"},
            ],
            "wf-ap-1": [
                {"event_type": "workflow.started", "occurred_at": _now(), "detail": "AP exception created"},
            ],
        }
        self.decisions: dict[str, dict] = {}
        self.memory_records: dict[str, dict] = {}
        self.agent_runs: dict[str, dict] = {}
        self.audit_logs: dict[str, dict] = {}
        self.idempotency_keys: dict[str, str] = {}
        self.documents: dict[str, dict] = {
            "doc-policy-1": {
                "id": "doc-policy-1",
                "org_id": DEV_ORG_ID,
                "title": "AP Policy",
                "doc_type": "policy",
                "citation": "Payment > 50K needs CFO approval.",
                "tags": ["ap", "policy", "approval"],
            }
        }

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid4()}"


store = InMemoryStore()
