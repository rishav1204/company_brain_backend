from __future__ import annotations

import uuid

from app.modules.erp.journals.events.journal_events import emit_journal_created
from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository
from app.modules.erp.journals.repositories.journal_repository import journal_repository
from app.modules.erp.journals.validators.journal_validator import journal_validator


from app.core.config import settings
from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.modules.erp.security.company_scope import require_company_id_for_erp_write


class JournalService:
    def _journal_number(self) -> str:
        return "JN-" + uuid.uuid4().hex[:12].upper()

    def create_draft(
        self,
        org_id: str,
        *,
        created_by: str | None,
        journal_type: str,
        posting_date: str,
        description: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        currency_code: str = "INR",
        exchange_rate: float = 1.0,
        company_id: str | None = None,
        lines: list[dict] | None = None,
        idempotency_key: str | None = None,
        ai_confidence: dict | None = None,
    ) -> dict:
        if settings.erp_require_company_id:
            company_id = company_resolution_service.resolve_for_write(
                org_id,
                company_id=company_id,
                operation="journal.create_draft",
            )
        elif company_id:
            require_company_id_for_erp_write(
                org_id=org_id, company_id=company_id, operation="journal.create_draft"
            )
        if idempotency_key:
            existing = journal_repository.get_by_idempotency(org_id, idempotency_key=idempotency_key)
            if existing:
                return self.get(org_id, journal_id=str(existing["id"]))

        journal_validator.validate_journal_type(journal_type)
        if lines:
            journal_validator.validate_lines(lines)
            journal_validator.validate_accounts_postable(org_id, lines)

        journal = journal_repository.create(
            org_id,
            journal_number=self._journal_number(),
            journal_type=journal_type,
            posting_date=posting_date,
            description=description,
            source_type=source_type,
            source_id=source_id,
            currency_code=currency_code,
            exchange_rate=exchange_rate,
            created_by=created_by,
            company_id=company_id,
            idempotency_key=idempotency_key,
            ai_confidence=ai_confidence,
        )
        jid = str(journal["id"])
        if lines:
            journal_line_repository.replace_lines(org_id, journal_id=jid, lines=lines)

        emit_journal_created(org_id, jid, payload={"journal_type": journal_type, "source_type": source_type})
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=created_by or "erp.journals",
                action="journal.created",
                object_ref=f"erp:journal:{jid}",
                payload={"journal_number": journal.get("journal_number"), "journal_type": journal_type},
                entity_type="journal",
                entity_id=jid,
                source_service="erp.journals",
            )
        except Exception:
            pass
        return self.get(org_id, journal_id=jid)

    def get(self, org_id: str, *, journal_id: str) -> dict:
        journal = journal_repository.get(org_id, journal_id=journal_id)
        if not journal:
            raise ValueError("Journal not found")
        lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)
        return {"journal": journal, "lines": lines}

    def list(
        self,
        org_id: str,
        *,
        journal_status: str | None = None,
        journal_type: str | None = None,
        company_id: str | None = None,
        branch_ids: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        return journal_repository.list(
            org_id,
            journal_status=journal_status,
            journal_type=journal_type,
            company_id=company_id,
            branch_ids=branch_ids,
            limit=limit,
            offset=offset,
        )

    def update_draft(
        self,
        org_id: str,
        *,
        journal_id: str,
        posting_date: str | None = None,
        description: str | None = None,
        journal_type: str | None = None,
        lines: list[dict] | None = None,
    ) -> dict:
        journal = journal_repository.get(org_id, journal_id=journal_id)
        if not journal:
            raise ValueError("Journal not found")
        journal_validator.ensure_editable(str(journal.get("journal_status")))
        if journal_type:
            journal_validator.validate_journal_type(journal_type)
        if lines is not None:
            journal_validator.validate_lines(lines)
            journal_validator.validate_accounts_postable(org_id, lines)
            journal_line_repository.replace_lines(org_id, journal_id=journal_id, lines=lines)
            journal_repository.clear_ai_review_flag(org_id, journal_id=journal_id)
        journal_repository.update_draft(
            org_id,
            journal_id=journal_id,
            posting_date=posting_date,
            description=description,
            journal_type=journal_type,
        )
        return self.get(org_id, journal_id=journal_id)

    def cancel(self, org_id: str, *, journal_id: str) -> dict:
        journal = journal_repository.get(org_id, journal_id=journal_id)
        if not journal:
            raise ValueError("Journal not found")
        status = str(journal.get("journal_status"))
        if status in {"posted", "reversed"}:
            raise ValueError("Posted journals cannot be cancelled; use reversal")
        journal_repository.set_status(org_id, journal_id=journal_id, journal_status="cancelled")
        return self.get(org_id, journal_id=journal_id)


journal_service = JournalService()
