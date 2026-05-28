from __future__ import annotations

from app.modules.platform.integrations.connectors.ocr.documentai_impl import documentai_impl
from app.modules.platform.integrations.services.connector_registry import connector_registry


class GcpDocumentAiOcrConnector:
    connector_type = "ocr"
    provider_name = "gcp_documentai"

    def health(self) -> dict:
        return {"ready": documentai_impl.is_ready()}

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        return documentai_impl.extract_text(storage_path=storage_path, mime_type=mime_type)


connector_registry.register(GcpDocumentAiOcrConnector())

