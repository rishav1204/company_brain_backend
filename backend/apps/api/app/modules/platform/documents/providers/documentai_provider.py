from __future__ import annotations

from app.modules.platform.integrations.connectors.ocr.documentai_impl import documentai_impl


class DocumentAIProvider:
    # Back-compat shim: OCR providers live under Module 7 integrations.
    def is_ready(self) -> bool:
        return documentai_impl.is_ready()

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        return documentai_impl.extract_text(storage_path=storage_path, mime_type=mime_type)


documentai_provider = DocumentAIProvider()

