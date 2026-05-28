from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.services.memory_service import apply_memory_decay

router = APIRouter(tags=["memory-admin"])


@router.post("/memory/decay/run")
def run_memory_decay(context=Depends(build_request_context)) -> dict:
    summary = apply_memory_decay(org_id=context.org_id)
    return {
        "request_id": context.request_id,
        "summary": summary,
        "confidence": 0.93,
        "verification_status": "memory_lifecycle_applied",
    }
