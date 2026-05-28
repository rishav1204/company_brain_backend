from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.modules.platform.documents.services.storage_service import storage_service


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    raw: dict[str, Any] | None = None


class DocumentAiOcrImpl:
    def is_ready(self) -> bool:
        return bool(settings.gcp_project_id and settings.gcp_documentai_processor_id)

    def _client(self):
        from google.cloud import documentai

        client_kwargs: dict[str, Any] = {}
        if settings.gcp_credentials_json:
            info = json.loads(settings.gcp_credentials_json)
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_info(info)
            client_kwargs["credentials"] = creds
        return documentai.DocumentProcessorServiceClient(**client_kwargs)

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        import httpx
        from google.cloud import documentai

        signed_url = storage_service.signed_download_url(storage_path, expires_in_seconds=300)
        with httpx.Client(timeout=90) as client:
            resp = client.get(signed_url)
            resp.raise_for_status()
            content = resp.content

        client = self._client()
        name = client.processor_path(settings.gcp_project_id, settings.gcp_location, settings.gcp_documentai_processor_id)
        raw_document = documentai.RawDocument(content=content, mime_type=mime_type or "application/pdf")
        result = client.process_document(request=documentai.ProcessRequest(name=name, raw_document=raw_document))
        doc = result.document

        full_text = doc.text or ""
        pages: list[OCRPage] = []
        for idx, page in enumerate(doc.pages or [], start=1):
            parts: list[str] = []
            for paragraph in page.paragraphs or []:
                ta = paragraph.layout.text_anchor
                for seg in ta.text_segments or []:
                    start = int(seg.start_index or 0)
                    end = int(seg.end_index or 0)
                    if end > start:
                        parts.append(full_text[start:end])
            pages.append(OCRPage(page_number=idx, text="".join(parts).strip()))

        return {
            "text": full_text.strip(),
            "pages": len(pages) or 1,
            "provider": "gcp_documentai",
            "signed_url": signed_url,
            "page_outputs": [{"page_number": p.page_number, "text": p.text} for p in pages],
            "raw": {"entities_count": len(doc.entities or []), "mime_type": doc.mime_type},
        }


documentai_impl = DocumentAiOcrImpl()

