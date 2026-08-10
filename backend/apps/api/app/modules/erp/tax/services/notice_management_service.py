from __future__ import annotations



from app.modules.erp.ports.intelligence_registry import intelligence_registry

from app.modules.erp.tax.repositories.compliance_repository import tax_notice_repository





class NoticeManagementService:

    def _enrich_from_document(self, org_id: str, document_id: str | None) -> dict:

        if not document_id:

            return {}

        try:

            from app.modules.platform.documents.repositories.extraction_repository import extraction_repository



            ext = extraction_repository.latest_extraction(org_id, document_id) or {}

            extracted = ext.get("extracted_data") if isinstance(ext.get("extracted_data"), dict) else {}

            text = str(extracted.get("full_text") or extracted.get("text") or "")

            return {"document_text": text[:4000], "extracted_data": extracted}

        except Exception:

            return {}



    def create_notice(self, org_id: str, **fields) -> dict:

        doc_context = self._enrich_from_document(org_id, fields.get("document_id"))

        meta = {**(fields.get("metadata") or {}), **doc_context}

        analysis = intelligence_registry.tax().analyze_notice(notice_type=fields["notice_type"], metadata=meta)

        if doc_context.get("document_text"):

            analysis["summary"] = f"{analysis.get('summary', '')} Document excerpt reviewed."

        return tax_notice_repository.create(

            org_id,

            notice_type=fields["notice_type"],

            received_date=fields["received_date"],

            document_id=fields.get("document_id"),

            ai_summary=analysis.get("summary"),

            metadata={**meta, "analysis": analysis},

        )



    def list_notices(self, org_id: str) -> list[dict]:

        return tax_notice_repository.list(org_id)





notice_management_service = NoticeManagementService()

