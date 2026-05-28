from dataclasses import dataclass, asdict

from app.services.repositories import invoices_repo, workflows_repo


@dataclass
class ObjectContext:
    object_type: str
    object_id: str
    amount: float | None = None
    vendor_risk: str | None = None
    owner_user_id: str | None = None
    status: str | None = None
    workflow_type: str | None = None
    invoice_type: str | None = None
    branch_id: str | None = None
    company_id: str | None = None

    def as_summary(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


def _normalize_owner(org_id: str, owner: str | None) -> str | None:
    if not owner:
        return None
    try:
        from app.modules.core.iam.services.identity_resolver import resolve_user_id

        return resolve_user_id(org_id, owner) or owner
    except Exception:
        return owner


def resolve_object_context(org_id: str, object_type: str, object_id: str) -> ObjectContext:
    normalized_type = object_type.lower().strip()
    normalized_id = object_id.strip()
    if normalized_type == "invoice":
        row = invoices_repo.get_invoice_policy_context(org_id=org_id, invoice_id=normalized_id)
        if row:
            return ObjectContext(
                object_type=object_type,
                object_id=normalized_id,
                amount=row.get("amount"),
                vendor_risk=row.get("vendor_risk"),
                status=row.get("status"),
                invoice_type=row.get("invoice_type"),
            )
    if normalized_type == "workflow":
        row = workflows_repo.get_workflow(org_id=org_id, workflow_id=normalized_id)
        if row:
            metadata = row.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            return ObjectContext(
                object_type=object_type,
                object_id=normalized_id,
                owner_user_id=_normalize_owner(org_id, row.get("owner_user_id")),
                status=row.get("state"),
                workflow_type=row.get("workflow_type"),
                branch_id=metadata.get("branch_id") or row.get("branch_id"),
                company_id=metadata.get("company_id") or row.get("company_id"),
            )
    return ObjectContext(object_type=object_type, object_id=normalized_id)
