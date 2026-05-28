from __future__ import annotations

from app.core.config import settings
from app.modules.platform.documents.services.storage_service import storage_service
from app.modules.platform.integrations.services.connector_registry import connector_registry
from app.services.llm_provider import llm_provider


def _hybrid_validate_text(*, text: str, mime_type: str, signed_url: str | None) -> str:
    """
    Optional second-pass cleanup: normalize OCR output and remove obvious noise.
    This is NOT a source-of-truth extractor (no accounting actions) — only improves text quality.
    """
    if not settings.ocr_hybrid_validate:
        return text
    if not llm_provider.is_ready():
        return text
    if not text.strip():
        return text
    try:
        client = llm_provider.client
        if client is None:
            return text
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You clean OCR text. Keep all content, but fix obvious OCR artifacts, "
                        "normalize whitespace, preserve line breaks, and do not hallucinate."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"MIME: {mime_type}\n"
                        f"SignedURL (optional context): {signed_url or ''}\n\n"
                        "OCR TEXT:\n"
                        f"{text}"
                    ),
                },
            ],
            temperature=0.0,
            timeout=settings.llm_timeout_seconds,
        )
        out = (resp.choices[0].message.content or "").strip()
        return out or text
    except Exception:
        return text


class OCRProvider:
    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        signed_url = storage_service.signed_download_url(storage_path, expires_in_seconds=300)
        mt = (mime_type or "").lower()

        provider = (settings.ocr_provider or "auto").lower()
        if provider in {"aws_textract"}:
            try:
                c = connector_registry.resolve_ocr(provider_name="aws_textract")
                if c is None:
                    raise RuntimeError("aws_textract OCR connector not registered")
                out = c.extract_text(storage_path=storage_path, mime_type=mime_type)
                out["text"] = _hybrid_validate_text(text=out.get("text", ""), mime_type=mime_type, signed_url=out.get("signed_url"))
                return out
            except Exception:
                pass
        if provider in {"gcp_documentai"}:
            try:
                c = connector_registry.resolve_ocr(provider_name="gcp_documentai")
                if c is None:
                    raise RuntimeError("gcp_documentai OCR connector not registered")
                out = c.extract_text(storage_path=storage_path, mime_type=mime_type)
                out["text"] = _hybrid_validate_text(text=out.get("text", ""), mime_type=mime_type, signed_url=out.get("signed_url"))
                return out
            except Exception:
                pass

        if mt in {"application/pdf"}:
            try:
                import io

                import httpx
                from pypdf import PdfReader

                with httpx.Client(timeout=30) as client:
                    resp = client.get(signed_url)
                    resp.raise_for_status()
                    raw = resp.content
                reader = PdfReader(io.BytesIO(raw))
                pages_text: list[str] = []
                for p in reader.pages[:50]:
                    pages_text.append(p.extract_text() or "")
                text = "\n\n".join(pages_text).strip()
                text = _hybrid_validate_text(text=text, mime_type=mime_type, signed_url=signed_url)
                return {"text": text, "pages": len(reader.pages), "provider": "pypdf", "signed_url": signed_url}
            except Exception:
                # fall through to other strategies
                pass
        if llm_provider.is_ready() and mt.startswith("image/"):
            # Use OpenAI vision for OCR on images (Phase 1 working OCR).
            try:
                client = llm_provider.client
                if client is None:
                    raise RuntimeError("LLM client not configured")
                response = client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": "You are an OCR engine. Extract all readable text. Return plain text only."},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract all text from this document image."},
                                {"type": "image_url", "image_url": {"url": signed_url}},
                            ],
                        },
                    ],
                    temperature=0.0,
                    timeout=settings.llm_timeout_seconds,
                )
                text = response.choices[0].message.content or ""
                text = _hybrid_validate_text(text=text.strip(), mime_type=mime_type, signed_url=signed_url)
                return {"text": text, "pages": 1, "provider": "openai_vision", "signed_url": signed_url}
            except Exception:
                pass
        if provider == "auto":
            # Try cloud OCR backends if configured, then fall back.
            for name in ("gcp_documentai", "aws_textract"):
                try:
                    c = connector_registry.resolve_ocr(provider_name=name)
                    if c is None:
                        continue
                    out = c.extract_text(storage_path=storage_path, mime_type=mime_type)
                    out["text"] = _hybrid_validate_text(text=out.get("text", ""), mime_type=mime_type, signed_url=out.get("signed_url"))
                    return out
                except Exception:
                    continue
        # Fallback: provider-neutral stub (PDF/text OCR providers can be added here).
        pseudo_text = f"OCR placeholder for {storage_path} ({mime_type}). Fetch via signed_url={signed_url}"
        pseudo_text = _hybrid_validate_text(text=pseudo_text, mime_type=mime_type, signed_url=signed_url)
        return {"text": pseudo_text, "pages": 1, "provider": "stub", "signed_url": signed_url}


ocr_provider = OCRProvider()
