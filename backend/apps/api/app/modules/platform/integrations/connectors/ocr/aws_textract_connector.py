from __future__ import annotations

from app.modules.platform.integrations.connectors.ocr.textract_impl import textract_impl
from app.modules.platform.integrations.services.connector_registry import connector_registry


class AwsTextractOcrConnector:
    connector_type = "ocr"
    provider_name = "aws_textract"

    def health(self) -> dict:
        return {"ready": textract_impl.is_ready()}

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        return textract_impl.extract_text(storage_path=storage_path, mime_type=mime_type)


connector_registry.register(AwsTextractOcrConnector())

