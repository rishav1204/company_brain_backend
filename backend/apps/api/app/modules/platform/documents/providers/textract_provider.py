from __future__ import annotations

# Back-compat shim: OCR providers live under Module 7 integrations.
from app.modules.platform.integrations.connectors.ocr.textract_impl import textract_impl


class TextractProvider:
    def is_ready(self) -> bool:
        return textract_impl.is_ready()

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        return textract_impl.extract_text(storage_path=storage_path, mime_type=mime_type)


textract_provider = TextractProvider()
