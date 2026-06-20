from app.services.integration_service import IntegrationResult, integration_service
from app.modules.core.iam.services.access_control import evaluate_access
from app.services.object_context import ObjectContext
from app.services.repositories import audit_repo


def execute_action(
    org_id: str,
    actor_id: str,
    tool: str,
    method: str,
    params: dict,
    attrs: dict | None = None,
    roles: list[str] | None = None,
    human_approved: bool = False,
) -> dict:
    normalized_tool = str(tool)
    normalized_method = str(method)
    if normalized_tool == "email" and normalized_method == "postMessage":
        normalized_method = "send"
    if normalized_tool == "erp" and normalized_method == "updateStatus":
        normalized_method = "writeback"
    action_name = f"{normalized_tool}.{normalized_method}"
    amount_raw = params.get("amount")
    parsed_amount: float | None = None
    if amount_raw is not None and str(amount_raw).strip():
        try:
            parsed_amount = float(amount_raw)
        except (TypeError, ValueError):
            parsed_amount = None
    object_context = ObjectContext(
        object_type=str(params.get("object_type", "action")),
        object_id=str(params.get("object_id", "")),
        amount=parsed_amount,
        vendor_risk=str(params.get("vendor_risk")) if params.get("vendor_risk") else None,
        owner_user_id=str(params.get("created_by") or params.get("owner_user_id") or "") or None,
        branch_id=str(params.get("branch_id")) if params.get("branch_id") else None,
        company_id=str(params.get("company_id")) if params.get("company_id") else None,
    )
    decision = evaluate_access(
        org_id=org_id,
        user_id=actor_id,
        roles=roles or ["tenant_admin"],
        action=action_name,
        object_context=object_context,
        attrs=attrs,
        created_by=object_context.owner_user_id,
        human_approved=human_approved,
    )
    if not decision.allowed:
        result = IntegrationResult(status="error", target=tool, detail="abac_denied")
        audit_repo.create_log(
            org_id=org_id,
            actor_type="agent",
            actor_id=actor_id,
            event_type="agent.action.denied",
            object_ref=f"integration:{normalized_tool}.{normalized_method}",
            payload_jsonb={
                "params": params,
                "status": result.status,
                "detail": decision.reason,
                "target": result.target,
                "checks": decision.checks or [],
            },
        )
        return {
            "status": result.status,
            "target": result.target,
            "detail": decision.reason,
            "response_code": result.response_code,
        }
    result: IntegrationResult
    if normalized_tool == "slack" and normalized_method == "postMessage":
        result = integration_service.send_slack(channel=str(params.get("channel", "#finance-alerts")), text=str(params.get("text", "")))
    elif normalized_tool == "email" and normalized_method == "send":
        result = integration_service.send_email(
            to=str(params.get("to", "")),
            subject=str(params.get("subject", "Finance notification")),
            body=str(params.get("body", "")),
        )
    elif normalized_tool == "jira" and normalized_method == "createIssue":
        result = integration_service.create_jira_issue(
            summary=str(params.get("summary", "Finance action")),
            description=str(params.get("description", "")),
        )
    elif normalized_tool == "linear" and normalized_method == "createIssue":
        result = integration_service.create_linear_issue(
            title=str(params.get("title", "Finance action")),
            description=str(params.get("description", "")),
        )
    elif normalized_tool == "erp" and normalized_method == "writeback":
        result = integration_service.push_erp(params)
    elif normalized_tool == "memory" and normalized_method == "search":
        from app.modules.finance_os.memory.services.retrieval_service import search_memories

        hits = search_memories(
            org_id,
            str(params.get("query", "")),
            memory_type=params.get("memory_type"),
            entity_type=params.get("entity_type"),
            entity_id=params.get("entity_id"),
            top_k=int(params.get("top_k", 5)),
        )
        return {"status": "completed", "target": "memory", "detail": "search", "items": hits}
    elif normalized_tool == "graph" and normalized_method == "traverse":
        from app.modules.finance_os.graph.services.lineage_service import lineage

        entity_id = str(params.get("entity_id") or params.get("entityId") or "")
        result = lineage(org_id, entity_id, max_depth=int(params.get("max_depth", 5)))
        return {"status": "completed", "target": "graph", "detail": "traverse", "result": result}
    else:
        result = IntegrationResult(status="error", target=normalized_tool, detail=f"unsupported_tool_or_method:{normalized_tool}.{normalized_method}")

    audit_repo.create_log(
        org_id=org_id,
        actor_type="agent",
        actor_id=actor_id,
        event_type="agent.action.executed" if result.status == "completed" else "agent.action.failed",
        object_ref=f"integration:{normalized_tool}.{normalized_method}",
        payload_jsonb={
            "params": params,
            "status": result.status,
            "detail": result.detail,
            "target": result.target,
            "checks": decision.checks or [],
        },
    )
    return {
        "status": result.status,
        "target": result.target,
        "detail": result.detail,
        "response_code": result.response_code,
    }
