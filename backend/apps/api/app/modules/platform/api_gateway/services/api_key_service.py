from __future__ import annotations

from app.modules.platform.integrations.services.api_key_service import api_key_service as integrations_api_key_service
from app.modules.platform.integrations.repositories.api_key_repository import api_key_repository


class ApiKeyService:
    def create(
        self,
        org_id: str,
        *,
        name: str,
        scopes: list[str],
        key_tier: str = "partner",
        ip_allowlist: list[str] | None = None,
        rate_limit_per_minute: int = 100,
        rate_limit_per_hour: int = 1000,
    ) -> tuple[dict, str]:
        item, raw_key = integrations_api_key_service.create(org_id, name=name, scopes=scopes)
        if api_key_repository.schema_ready():
            api_key_repository.update_gateway_fields(
                org_id,
                api_key_id=str(item.get("id")),
                key_tier=key_tier,
                ip_allowlist=ip_allowlist or [],
                rate_limit_per_minute=rate_limit_per_minute,
                rate_limit_per_hour=rate_limit_per_hour,
            )
        try:
            from app.modules.platform.api_gateway.events.gateway_events import gateway_events

            gateway_events.emit_key_created(org_id, api_key_id=str(item.get("id")))
        except Exception:
            pass
        return item, raw_key

    def list(self, org_id: str) -> list[dict]:
        return api_key_repository.list(org_id)

    def revoke(self, org_id: str, *, api_key_id: str) -> dict:
        item = integrations_api_key_service.revoke(org_id, api_key_id=api_key_id)
        try:
            from app.modules.platform.api_gateway.events.gateway_events import gateway_events

            gateway_events.emit_key_revoked(org_id, api_key_id=api_key_id)
        except Exception:
            pass
        return item


api_key_service = ApiKeyService()
