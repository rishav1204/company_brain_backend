from __future__ import annotations

import hashlib

from app.modules.erp.banking.engine.bank_feed_engine import normalize_batch
from app.modules.erp.banking.engine.statement_engine import parse_csv_statement, parse_excel_statement, parse_mt940
from app.modules.erp.banking.events.banking_events import emit_bank_statement_imported, emit_bank_transaction_imported
from app.modules.erp.banking.repositories.beneficiary_repository import statement_import_repository
from app.modules.erp.banking.services.bank_feed_service import bank_feed_service
from app.modules.erp.banking.services.transaction_service import transaction_service


class StatementImportService:
    def import_file(
        self,
        org_id: str,
        *,
        bank_account_id: str,
        file_format: str,
        content: bytes | str,
        imported_by: str | None = None,
        column_map: dict | None = None,
    ) -> dict:
        fmt = file_format.lower()
        if fmt == "csv":
            text = content.decode("utf-8") if isinstance(content, bytes) else content
            rows = parse_csv_statement(text, column_map=column_map)
        elif fmt in {"xlsx", "excel"}:
            if not isinstance(content, bytes):
                raise ValueError("Excel import requires binary content")
            rows = parse_excel_statement(content)
        elif fmt == "mt940":
            text = content.decode("utf-8") if isinstance(content, bytes) else content
            rows = parse_mt940(text)
        elif fmt == "pdf":
            raise ValueError("PDF statement import not yet supported")
        else:
            raise ValueError(f"Unsupported format: {file_format}")
        canonical = normalize_batch(rows)
        file_hash = hashlib.sha256(content if isinstance(content, bytes) else content.encode()).hexdigest()
        imported = 0
        skipped = 0
        for row in canonical:
            key = f"stmt:{file_hash}:{row.get('reference')}:{row.get('date')}:{row.get('amount')}:{row.get('type')}"
            try:
                transaction_service.import_canonical(org_id, bank_account_id=bank_account_id, row=row, idempotency_key=key, source="statement_import")
                imported += 1
            except Exception:
                skipped += 1
        audit_row = statement_import_repository.create(
            org_id,
            bank_account_id=bank_account_id,
            file_format=fmt,
            file_hash=file_hash,
            row_count=len(canonical),
            imported_count=imported,
            skipped_count=skipped,
            imported_by=imported_by,
        )
        emit_bank_statement_imported(org_id, import_id=str(audit_row["id"]), bank_account_id=bank_account_id, count=imported)
        emit_bank_transaction_imported(org_id, bank_account_id=bank_account_id, count=imported)
        return {"import_id": audit_row["id"], "imported": imported, "skipped": skipped, "row_count": len(canonical)}


statement_import_service = StatementImportService()
