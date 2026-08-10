from __future__ import annotations

from typing import Any

from app.modules.platform.control_plane.repositories.control_plane_repository import (
    control_plane_repository,
)


class ActivityService:
    def record(self, **kwargs: Any) -> dict[str, Any]:
        try:
            return control_plane_repository.record_activity(**kwargs)
        except Exception:
            return {}

    def list_for_org(self, org_id: str, **kwargs) -> list[dict[str, Any]]:
        return control_plane_repository.list_activity(org_id=org_id, **kwargs)

    def list_all(self, **kwargs) -> list[dict[str, Any]]:
        return control_plane_repository.list_activity(**kwargs)


activity_service = ActivityService()
