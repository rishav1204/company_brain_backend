from __future__ import annotations

from fastapi import APIRouter

from app.modules.platform.integrations.services.connector_registry import connector_registry

router = APIRouter()


@router.get("/registry")
def list_registry() -> dict:
    return {"items": connector_registry.list()}

