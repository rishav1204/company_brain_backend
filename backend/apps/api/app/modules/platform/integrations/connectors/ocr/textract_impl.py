from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.modules.platform.documents.providers.s3_provider import parse_s3_storage_path, s3_provider
from app.modules.platform.documents.services.storage_service import storage_service


@dataclass(frozen=True)
class OCRPage:
    page_number: int
    text: str
    raw: dict[str, Any] | None = None


class TextractOcrImpl:
    def is_ready(self) -> bool:
        if not settings.aws_region.strip():
            return False
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            return True
        # EC2 instance profile / default credential chain
        return bool(settings.textract_s3_bucket.strip() or settings.documents_s3_bucket.strip())

    def _session_kwargs(self) -> dict[str, Any]:
        session_kwargs: dict[str, Any] = {}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            session_kwargs["aws_session_token"] = settings.aws_session_token
        if settings.aws_region:
            session_kwargs["region_name"] = settings.aws_region
        return session_kwargs

    def _textract_client(self):
        import boto3

        return boto3.client("textract", **self._session_kwargs())

    def _blocks_to_result(self, blocks: list[dict], *, signed_url: str, raw_meta: dict | None = None) -> dict:
        pages: dict[int, list[str]] = {}
        for block in blocks:
            if block.get("BlockType") != "LINE":
                continue
            page_num = int(block.get("Page") or 1)
            pages.setdefault(page_num, []).append(block.get("Text") or "")
        page_objs: list[OCRPage] = [
            OCRPage(page_number=pn, text="\n".join(pages[pn]).strip()) for pn in sorted(pages)
        ]
        full_text = "\n\n".join([p.text for p in page_objs]).strip()
        return {
            "text": full_text,
            "pages": len(page_objs) or 1,
            "provider": "aws_textract",
            "signed_url": signed_url,
            "page_outputs": [{"page_number": p.page_number, "text": p.text} for p in page_objs],
            "raw": raw_meta or {},
        }

    def _extract_from_bytes(self, *, content: bytes, signed_url: str) -> dict:
        textract = self._textract_client()
        result = textract.detect_document_text(Document={"Bytes": content})
        blocks = result.get("Blocks") or []
        return self._blocks_to_result(
            blocks,
            signed_url=signed_url,
            raw_meta={
                "mode": "bytes",
                "document_metadata": result.get("DocumentMetadata"),
                "warnings": result.get("Warnings"),
            },
        )

    def _poll_text_detection(self, *, job_id: str, textract) -> list[dict]:
        blocks: list[dict] = []
        next_token: str | None = None
        status = "IN_PROGRESS"
        deadline = time.time() + 120
        while status == "IN_PROGRESS" and time.time() < deadline:
            time.sleep(2)
            kwargs: dict[str, Any] = {"JobId": job_id}
            if next_token:
                kwargs["NextToken"] = next_token
            response = textract.get_document_text_detection(**kwargs)
            status = str(response.get("JobStatus") or "IN_PROGRESS")
            if status == "FAILED":
                raise RuntimeError(f"Textract job failed: {response.get('StatusMessage', 'unknown')}")
            blocks.extend(response.get("Blocks") or [])
            next_token = response.get("NextToken")
            if status == "SUCCEEDED" and not next_token:
                break
        if status != "SUCCEEDED":
            raise RuntimeError(f"Textract job did not complete: {status}")
        while next_token:
            response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
            blocks.extend(response.get("Blocks") or [])
            next_token = response.get("NextToken")
        return blocks

    def _extract_from_s3(self, *, bucket: str, object_key: str, signed_url: str) -> dict:
        textract_bucket = s3_provider.textract_bucket()
        staging_key = s3_provider.staging_key_for_textract(source_bucket=bucket, source_key=object_key)
        if bucket != textract_bucket or not object_key.startswith("textract-staging/"):
            s3_provider.copy_object(
                source_bucket=bucket,
                source_key=object_key,
                dest_bucket=textract_bucket,
                dest_key=staging_key,
            )
        textract = self._textract_client()
        start = textract.start_document_text_detection(
            DocumentLocation={"S3Object": {"Bucket": textract_bucket, "Name": staging_key}}
        )
        job_id = str(start.get("JobId") or "")
        if not job_id:
            raise RuntimeError("Textract did not return a job id")
        blocks = self._poll_text_detection(job_id=job_id, textract=textract)
        return self._blocks_to_result(
            blocks,
            signed_url=signed_url,
            raw_meta={"mode": "s3_async", "job_id": job_id, "staging_key": staging_key},
        )

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict:
        signed_url = storage_service.signed_download_url(storage_path, expires_in_seconds=300)
        parsed = parse_s3_storage_path(storage_path)
        if parsed and settings.textract_s3_bucket.strip():
            bucket, object_key = parsed
            return self._extract_from_s3(bucket=bucket, object_key=object_key, signed_url=signed_url)

        import httpx

        with httpx.Client(timeout=60) as client:
            resp = client.get(signed_url)
            resp.raise_for_status()
            content = resp.content

        mt = (mime_type or "").lower()
        if parsed and mt == "application/pdf" and settings.textract_s3_bucket.strip():
            bucket, object_key = parsed
            return self._extract_from_s3(bucket=bucket, object_key=object_key, signed_url=signed_url)

        return self._extract_from_bytes(content=content, signed_url=signed_url)


textract_impl = TextractOcrImpl()
