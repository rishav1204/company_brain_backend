from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.services.policy_service import abac_allows
from app.services.connectors import run_connector
from app.services.repositories import audit_repo

router = APIRouter(tags=["connectors"])


class ConnectorRunRequest(BaseModel):
    connector: str
    mode: str = "polling"
    source_id: str | None = None


@router.post("/connectors/run")
def connectors_run(request: ConnectorRunRequest, context=Depends(build_request_context)) -> dict:
    if not abac_allows(context.attrs, action="connectors.run", object_type="connector"):
        raise HTTPException(status_code=403, detail="ABAC denies connector execution")
    result = run_connector(org_id=context.org_id, connector=request.connector, mode=request.mode, source_id=request.source_id)
    if result.status != "completed":
        audit_repo.create_log(
            org_id=context.org_id,
            actor_type="user",
            actor_id=context.user_id,
            event_type="connector.run.failed",
            object_ref=f"connector:{request.connector}",
            payload_jsonb={"mode": request.mode, "source_id": request.source_id, "detail": result.detail},
        )
        raise HTTPException(status_code=503, detail=f"Connector failed: {result.detail}")
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="connector.run.completed",
        object_ref=f"connector:{request.connector}",
        payload_jsonb={"mode": request.mode, "source_id": request.source_id, "records_ingested": result.records_ingested},
    )
    return {
        "request_id": context.request_id,
        "org_id": context.org_id,
        "connector": result.connector,
        "status": result.status,
        "source_id": request.source_id,
        "records_ingested": result.records_ingested,
        "detail": result.detail,
        "confidence": 0.9 if result.status == "completed" else 0.6,
        "verification_status": "connector_sync_completed" if result.status == "completed" else "connector_sync_failed",
    }
