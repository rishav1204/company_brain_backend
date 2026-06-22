from __future__ import annotations

from typing import Any, Callable

from fastapi import HTTPException

from app.modules.platform.api_gateway.security.gateway_access import enforce_gateway_action
from app.modules.platform.api_gateway.services.api_request_log_service import api_request_log_service


class ApiGatewayEngine:
    def process_external_request(
        self,
        context,
        *,
        action: str,
        method: str,
        path: str,
        handler: Callable[[], dict[str, Any]],
        required_scopes: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        enforce_gateway_action(
            context,
            action=action,
            required_scopes=required_scopes,
        )
        try:
            result = handler()
            if idempotency_key:
                try:
                    from app.modules.platform.events.services.idempotency_service import platform_idempotency_service

                    platform_idempotency_service.store(
                        context.org_id,
                        "api_gateway",
                        idempotency_key,
                        request_payload={"action": action, "path": path},
                        response_payload=result,
                    )
                except Exception:
                    pass
            api_request_log_service.record(
                context.org_id,
                api_key_id=getattr(context, "api_key_id", None),
                method=method,
                path=path,
                status_code=200,
                scope_used=required_scopes or list(context.api_key_scopes or []),
                idempotency_key=idempotency_key,
                ip_address=getattr(context, "ip_address", None),
            )
            return result
        except HTTPException as exc:
            api_request_log_service.record(
                context.org_id,
                api_key_id=getattr(context, "api_key_id", None),
                method=method,
                path=path,
                status_code=exc.status_code,
                scope_used=required_scopes or [],
                idempotency_key=idempotency_key,
                ip_address=getattr(context, "ip_address", None),
            )
            raise


api_gateway_engine = ApiGatewayEngine()
