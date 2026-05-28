from __future__ import annotations

from app.modules.platform.documents.repositories.document_repository import document_repository
from app.modules.platform.documents.repositories.evidence_repository import evidence_repository
from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
from app.services.llm_provider import llm_provider


class DuplicateDetectionService:
    def _norm_invoice(self, value: str) -> str:
        v = "".join(ch for ch in (value or "").lower().strip() if ch.isalnum())
        return v.lstrip("0") or v

    def _invoice_fuzzy_match(self, a: str, b: str) -> bool:
        na = self._norm_invoice(a)
        nb = self._norm_invoice(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        # Allow small OCR noise (one char off) for reasonably sized invoice ids.
        if abs(len(na) - len(nb)) > 1 or min(len(na), len(nb)) < 6:
            return False
        mismatches = sum(1 for x, y in zip(na, nb) if x != y) + abs(len(na) - len(nb))
        return mismatches <= 1

    def detect(self, org_id: str, *, document_id: str) -> dict | None:
        current = document_repository.get_document(org_id, document_id)
        if not current:
            return None
        items = document_repository.list_documents(org_id, limit=200, document_type=str(current.get("document_type", "")))
        checksum = str(current.get("checksum_hash", ""))
        current_ext = extraction_repository.latest_extraction(org_id, document_id) or {}
        current_data = current_ext.get("extracted_data") if isinstance(current_ext.get("extracted_data"), dict) else {}
        inv_no = str((current_data or {}).get("invoice_number") or "").strip()
        gstin = str((current_data or {}).get("gstin") or "").strip().upper()
        total = float((current_data or {}).get("total_amount") or 0)
        vendor = str((current_data or {}).get("vendor_name") or (current_data or {}).get("supplier_name") or "").strip().lower()

        for item in items:
            if str(item.get("id")) == document_id:
                continue
            if str(item.get("checksum_hash", "")) == checksum:
                return evidence_repository.create_duplicate_candidate(
                    org_id,
                    document_id=document_id,
                    matched_document_id=str(item.get("id")),
                    duplicate_reason="checksum_match",
                    similarity_score=1.0,
                )
            # Field-based duplicate detection (invoice number + gstin + amount)
            other_ext = extraction_repository.latest_extraction(org_id, str(item.get("id"))) or {}
            other_data = other_ext.get("extracted_data") if isinstance(other_ext.get("extracted_data"), dict) else {}
            other_inv = str((other_data or {}).get("invoice_number") or "").strip()
            other_gstin = str((other_data or {}).get("gstin") or "").strip().upper()
            other_total = float((other_data or {}).get("total_amount") or 0)
            other_vendor = str(
                (other_data or {}).get("vendor_name") or (other_data or {}).get("supplier_name") or ""
            ).strip().lower()

            if inv_no and other_inv and self._invoice_fuzzy_match(inv_no, other_inv):
                if (not gstin or not other_gstin or gstin == other_gstin) and abs(total - other_total) < 0.01:
                    # Distinguish "reupload" (same invoice id) vs "true duplicate" (same checksum).
                    return evidence_repository.create_duplicate_candidate(
                        org_id,
                        document_id=document_id,
                        matched_document_id=str(item.get("id")),
                        duplicate_reason="invoice_fuzzy_gstin_amount_match",
                        similarity_score=0.94,
                    )
                # We still want to flag as possible duplicate if vendor matches and totals close.
                if vendor and other_vendor and vendor == other_vendor and abs(total - other_total) < 0.5:
                    return evidence_repository.create_duplicate_candidate(
                        org_id,
                        document_id=document_id,
                        matched_document_id=str(item.get("id")),
                        duplicate_reason="invoice_fuzzy_vendor_amount_match",
                        similarity_score=0.85,
                    )

        # Optional semantic similarity (best-effort)
        if llm_provider.is_ready() and current_data:
            text = f"invoice_number={inv_no} gstin={gstin} total={total} vendor={vendor}"
            emb = llm_provider.generate_embedding(org_id=org_id, text=text)
            # Prefer chunk-level similarity across OCR text (more robust than doc-level metadata).
            matches = extraction_repository.search_chunk_embeddings(org_id, query_embedding=emb, top_k=5)
            for m in matches:
                mid = str(m.get("document_id", ""))
                if mid and mid != document_id:
                    dist = float(m.get("distance") or 999)
                    if dist < 0.15:
                        return evidence_repository.create_duplicate_candidate(
                            org_id,
                            document_id=document_id,
                            matched_document_id=mid,
                            duplicate_reason="semantic_similarity",
                            similarity_score=max(0.0, 1.0 - dist),
                        )
        return None


duplicate_detection_service = DuplicateDetectionService()
