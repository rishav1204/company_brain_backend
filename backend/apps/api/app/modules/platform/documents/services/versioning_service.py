from __future__ import annotations

from app.modules.platform.documents.repositories.document_repository import document_repository


class VersioningService:
    def create_version(
        self,
        org_id: str,
        *,
        document_id: str,
        storage_path: str,
        uploaded_by: str | None,
        change_reason: str,
        metadata: dict | None = None,
    ) -> dict:
        version = document_repository.create_version(
            org_id,
            document_id=document_id,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            change_reason=change_reason,
            metadata=metadata or {},
        )
        try:
            document_repository.set_current_version(
                org_id,
                document_id=document_id,
                storage_path=storage_path,
                version_number=int(version.get("version_number") or 1),
            )
        except Exception:
            pass
        return version


versioning_service = VersioningService()
