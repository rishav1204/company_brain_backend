from __future__ import annotations

from app.modules.platform.api_gateway.repositories.api_request_log_repository import api_request_log_repository
from app.modules.platform.governance.services.audit_service import audit_service
from app.modules.platform.governance.utils.object_ref import format_object_ref


class ApiRequestLogService:
    def record(
        self,
        org_id: str,
        *,
        api_key_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        scope_used: list[str] | None = None,
        idempotency_key: str | None = None,
        ip_address: str | None = None,
    ) -> dict:
        row = api_request_log_repository.record(
            org_id,
            api_key_id=api_key_id,
            method=method,
            path=path,
            status_code=status_code,
            scope_used=scope_used,
            idempotency_key=idempotency_key,
            ip_address=ip_address,
        )
        try:
            audit_service.record(
                org_id=org_id,
                actor_type="api_key" if api_key_id else "user",
                actor_id=api_key_id or "gateway",
                action="api.request",
                object_ref=format_object_ref("platform", "api_request", row.get("id", "")),
                payload={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "scopes": scope_used,
                },
                entity_type="api_request",
                entity_id=row.get("id"),
                source_service="api_gateway",
            )
        except Exception:
            pass
        return row


api_request_log_service = ApiRequestLogService()
