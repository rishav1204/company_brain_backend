from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.memory.schemas.memory_schema import MemorySearchResponse
from app.modules.finance_os.memory.security.memory_guard import require_memory_read
from app.modules.finance_os.memory.services.retrieval_service import search_memories

router = APIRouter(tags=["finance-os-memory-retrieval"])


@router.get("/search", response_model=MemorySearchResponse)
def search_memory(
    q: str,
    memory_type: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    top_k: int = 10,
    context=Depends(build_request_context),
) -> MemorySearchResponse:
    require_memory_read(context.user)
    items = search_memories(
        context.org_id,
        q,
        memory_type=memory_type,
        entity_type=entity_type,
        entity_id=entity_id,
        top_k=top_k,
    )
    return MemorySearchResponse(items=items, query=q, count=len(items))
