from app.schemas.workflows import WorkflowItem


def present_workflow(row: dict) -> WorkflowItem:
    workflow_type = row["workflow_type"]
    state = row["state"]
    return WorkflowItem(
        id=row["id"],
        workflow_type=workflow_type,
        state=state,
        owner_user_id=row.get("owner_user_id"),
        started_at=row["started_at"],
        closed_at=row.get("closed_at"),
        type=workflow_type,
        status=state,
        org_id=row.get("org_id"),
        reference_number=row.get("reference_number"),
        amount=row.get("amount"),
        metadata=row.get("metadata") or {},
    )
