from __future__ import annotations

from app.modules.platform.integrations.repositories.connector_repository import connector_repository
from app.modules.platform.integrations.security.credential_manager import credential_manager


class ConnectorService:
    def create(
        self,
        org_id: str,
        *,
        connector_type: str,
        provider_name: str,
        config: dict,
        credentials: dict,
    ) -> dict:
        encrypted = None
        if credentials:
            encrypted = credential_manager.encrypt_json(credentials)
        return connector_repository.create(
            org_id,
            connector_type=connector_type,
            provider_name=provider_name,
            status="active",
            config=config or {},
            encrypted_credentials=encrypted,
        )

    def list(self, org_id: str) -> list[dict]:
        return connector_repository.list(org_id)


connector_service = ConnectorService()

