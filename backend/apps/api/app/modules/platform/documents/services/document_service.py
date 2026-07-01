from __future__ import annotations

import base64
import hashlib
import logging
from uuid import uuid4

from app.core.config import settings
from app.modules.platform.documents.events.document_events import (
    emit_document_uploaded,
    emit_duplicate_detected,
)
from app.modules.platform.documents.events.ocr_events import emit_ocr_requested
from app.modules.platform.documents.events.security_events import emit_malware_scan_requested
from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.services.duplicate_detection_service import duplicate_detection_service
from app.modules.platform.documents.services.malware_scan_service import malware_scan_service
from app.modules.platform.documents.services.storage_service import storage_service
from app.modules.platform.documents.services.versioning_service import versioning_service
from app.modules.platform.documents.validators.upload_validator import validate_decoded_upload_size, validate_upload_payload
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def _decode_base64_content(raw: str | None) -> bytes:
    if not raw:
        return b""
    try:
        return base64.b64decode(raw, validate=True)
    except Exception:
        return b""


def _ocr_extraction_type(document_type: str) -> str:
    dt = str(document_type or "").lower()
    if dt in {"receipt", "expense_receipt"}:
        return "receipt_ocr"
    return "invoice_ocr"


class DocumentService:
    def schema_ready(self) -> bool:
        return document_repository.schema_ready()

    def create_document(
        self,
        org_id: str,
        *,
        uploaded_by: str | None,
        document_type: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        base64_content: str | None = None,
        metadata: dict | None = None,
        enqueue_ocr: bool = True,
    ) -> dict:
        validate_upload_payload(file_name=file_name, mime_type=mime_type, file_size=file_size)
        raw = _decode_base64_content(base64_content)
        validate_decoded_upload_size(declared_size=file_size, decoded_size=len(raw))
        malware_scan_service.scan_or_raise(raw_bytes=raw, file_name=file_name, mime_type=mime_type)
        checksum_hash = hashlib.sha256(raw if raw else f"{file_name}:{file_size}:{uuid4()}".encode("utf-8")).hexdigest()
        upload = storage_service.upload(
            org_id=org_id,
            document_type=document_type,
            file_name=file_name,
            raw_bytes=raw,
            mime_type=mime_type,
        )
        retention_until = (datetime.now(timezone.utc) + timedelta(days=365 * 8)).isoformat()
        row, is_duplicate = document_repository.create_document(
            org_id,
            document_type=document_type,
            file_name=file_name,
            mime_type=mime_type,
            storage_path=str(upload["storage_path"]),
            checksum_hash=checksum_hash,
            uploaded_by=uploaded_by,
            file_size=file_size,
            metadata=metadata or {},
            malware_scan_status="clean" if raw else "pending",
            retention_until=retention_until,
        )
        if is_duplicate:
            logger.info(
                "Duplicate document upload replay org_id=%s checksum=%s type=%s document_id=%s",
                org_id,
                checksum_hash[:12],
                document_type,
                row.get("id"),
            )
            return {
                **row,
                "signed_url": storage_service.signed_download_url(str(row.get("storage_path", ""))),
                "requires_human_review": False,
                "confidence_threshold": settings.document_confidence_threshold,
                "duplicate": True,
                "idempotent_replay": True,
            }
        versioning_service.create_version(
            org_id,
            document_id=str(row["id"]),
            storage_path=str(upload["storage_path"]),
            uploaded_by=uploaded_by,
            change_reason="initial_upload",
            metadata=metadata or {},
        )
        emit_document_uploaded(
            org_id,
            document_id=str(row["id"]),
            document_type=document_type,
            storage_path=str(upload["storage_path"]),
        )
        duplicate = duplicate_detection_service.detect(org_id, document_id=str(row["id"]))
        if duplicate:
            emit_duplicate_detected(org_id, document_id=str(row["id"]), matched_document_id=str(duplicate.get("matched_document_id", "")))
        if enqueue_ocr:
            emit_ocr_requested(org_id, document_id=str(row["id"]), extraction_type=_ocr_extraction_type(document_type))
        return {
            **row,
            "signed_url": storage_service.signed_download_url(str(row.get("storage_path", ""))),
            "requires_human_review": False,
            "confidence_threshold": settings.document_confidence_threshold,
        }

    def list_documents(self, org_id: str, *, limit: int = 50, document_type: str | None = None) -> list[dict]:
        items = document_repository.list_documents(org_id, limit=limit, document_type=document_type)
        for item in items:
            item["signed_url"] = storage_service.signed_download_url(str(item.get("storage_path", "")))
        return items

    def create_new_version(
        self,
        org_id: str,
        *,
        document_id: str,
        uploaded_by: str | None,
        file_name: str,
        mime_type: str,
        file_size: int,
        base64_content: str | None,
        change_reason: str,
        metadata: dict | None = None,
    ) -> dict:
        validate_upload_payload(file_name=file_name, mime_type=mime_type, file_size=file_size)
        raw = _decode_base64_content(base64_content)
        validate_decoded_upload_size(declared_size=file_size, decoded_size=len(raw))
        malware_scan_service.scan_or_raise(raw_bytes=raw, file_name=file_name, mime_type=mime_type)
        upload = storage_service.upload(
            org_id=org_id,
            document_type="version",
            file_name=file_name,
            raw_bytes=raw,
            mime_type=mime_type,
        )
        return versioning_service.create_version(
            org_id,
            document_id=document_id,
            storage_path=str(upload["storage_path"]),
            uploaded_by=uploaded_by,
            change_reason=change_reason,
            metadata=metadata or {},
        )

    def finalize_cloudinary_upload(
        self,
        org_id: str,
        *,
        uploaded_by: str | None,
        document_type: str,
        file_name: str,
        mime_type: str,
        file_size: int,
        checksum_hash: str,
        resource_type: str,
        public_id: str,
        secure_url: str | None = None,
        metadata: dict | None = None,
        enqueue_ocr: bool = True,
    ) -> dict:
        validate_upload_payload(file_name=file_name, mime_type=mime_type, file_size=file_size)
        resource_type = (resource_type or "raw").strip().lower()
        # Enforce strong org isolation: public_id must live under the org/document_type folder we sign.
        expected_prefix = f"{settings.documents_bucket_prefix}/{org_id}/{document_type}/"
        if not public_id.startswith(expected_prefix):
            raise ValueError("Invalid public_id: org isolation policy violation")
        storage_path = f"cloudinary://{settings.cloudinary_cloud_name}/{resource_type}/{public_id}"
        retention_until = (datetime.now(timezone.utc) + timedelta(days=365 * 8)).isoformat()
        existing = document_repository.get_by_checksum(
            org_id,
            checksum_hash=checksum_hash,
            document_type=document_type,
        )
        if existing:
            logger.info(
                "Cloudinary finalize duplicate org_id=%s checksum=%s type=%s document_id=%s",
                org_id,
                checksum_hash[:12],
                document_type,
                existing.get("id"),
            )
            return {
                **existing,
                "signed_url": storage_service.signed_download_url(str(existing.get("storage_path", ""))),
                "duplicate": True,
                "idempotent_replay": True,
            }
        row, is_duplicate = document_repository.create_document(
            org_id,
            document_type=document_type,
            file_name=file_name,
            mime_type=mime_type,
            storage_path=storage_path,
            checksum_hash=checksum_hash,
            uploaded_by=uploaded_by,
            file_size=file_size,
            metadata={"cloudinary_secure_url": secure_url, **(metadata or {})},
            malware_scan_status="pending",
            retention_until=retention_until,
        )
        if is_duplicate:
            logger.info(
                "Cloudinary finalize race duplicate org_id=%s checksum=%s type=%s document_id=%s",
                org_id,
                checksum_hash[:12],
                document_type,
                row.get("id"),
            )
            return {
                **row,
                "signed_url": storage_service.signed_download_url(str(row.get("storage_path", ""))),
                "duplicate": True,
                "idempotent_replay": True,
            }
        versioning_service.create_version(
            org_id,
            document_id=str(row["id"]),
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            change_reason="direct_upload_finalize",
            metadata={"cloudinary_public_id": public_id, **(metadata or {})},
        )
        emit_document_uploaded(org_id, document_id=str(row["id"]), document_type=document_type, storage_path=storage_path)
        duplicate = duplicate_detection_service.detect(org_id, document_id=str(row["id"]))
        if duplicate:
            emit_duplicate_detected(
                org_id,
                document_id=str(row["id"]),
                matched_document_id=str(duplicate.get("matched_document_id", "")),
            )
        if enqueue_ocr:
            emit_ocr_requested(org_id, document_id=str(row["id"]), extraction_type=_ocr_extraction_type(document_type))
        # Request scan asynchronously for direct uploads.
        emit_malware_scan_requested(org_id, document_id=str(row["id"]))
        return {**row, "signed_url": storage_service.signed_download_url(storage_path)}


document_service = DocumentService()
