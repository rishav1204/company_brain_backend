from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.modules.platform.documents.services.storage_service import storage_service


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    raw: dict[str, Any] | None = None


class TextractOcrImpl:
    def is_ready(self) -> bool:
        return bool(settings.aws_region) and (
            bool(settings.aws_access_key_id and settings.aws_secret_access_key) or True
        )

    def _client(self):
        import boto3

        session_kwargs: dict[str, Any] = {}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            session_kwargs["aws_session_token"] = settings.aws_session_token
        if settings.aws_region:
            session_kwargs["region_name"] = settings.aws_region
        return boto3.client("textract", **session_kwargs)

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        import httpx

        signed_url = storage_service.signed_download_url(storage_path, expires_in_seconds=300)
        with httpx.Client(timeout=60) as client:
            resp = client.get(signed_url)
            resp.raise_for_status()
            content = resp.content

        textract = self._client()
        result = textract.detect_document_text(Document={"Bytes": content})
        blocks = result.get("Blocks") or []
        pages: dict[int, list[str]] = {}
        for b in blocks:
            if b.get("BlockType") != "LINE":
                continue
            page_num = int(b.get("Page") or 1)
            pages.setdefault(page_num, []).append(b.get("Text") or "")
        page_objs: list[OCRPage] = [OCRPage(page_number=pn, text="\n".join(pages[pn]).strip()) for pn in sorted(pages)]
        full_text = "\n\n".join([p.text for p in page_objs]).strip()
        return {
            "text": full_text,
            "pages": len(page_objs) or 1,
            "provider": "aws_textract",
            "signed_url": signed_url,
            "page_outputs": [{"page_number": p.page_number, "text": p.text} for p in page_objs],
            "raw": {"document_metadata": result.get("DocumentMetadata"), "warnings": result.get("Warnings")},
        }


textract_impl = TextractOcrImpl()

