from __future__ import annotations

from typing import Any

from app.modules.erp.consolidation.repositories.intercompany_repository import intercompany_repository


class IntercompanyService:
    def register(
        self,
        org_id: str,
        *,
        source_company_id: str,
        target_company_id: str,
        transaction_type: str,
        amount: float,
        currency: str = "INR",
        source_document_type: str | None = None,
        source_document_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        if source_company_id == target_company_id:
            raise ValueError("Intercompany source and target must differ")
        if amount <= 0:
            raise ValueError("Amount must be positive")
        row = intercompany_repository.create(
            org_id,
            source_company_id=source_company_id,
            target_company_id=target_company_id,
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
            metadata=metadata,
        )
        from app.modules.erp.consolidation.events import consolidation_events

        consolidation_events.emit_intercompany_created(org_id, transaction_id=row["id"])
        return row

    def list_transactions(
        self,
        org_id: str,
        *,
        source_company_id: str | None = None,
        target_company_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        return intercompany_repository.list_transactions(
            org_id,
            source_company_id=source_company_id,
            target_company_id=target_company_id,
            status=status,
        )

    def list_balances(self, org_id: str) -> list[dict[str, Any]]:
        return intercompany_repository.list_balances(org_id)

    def match(self, org_id: str, *, tx_id: str, matched_tx_id: str) -> dict[str, Any]:
        return intercompany_repository.match_pair(org_id, tx_id=tx_id, matched_tx_id=matched_tx_id)

    def detect_mismatches(self, org_id: str) -> list[dict[str, Any]]:
        balances = intercompany_repository.list_balances(org_id)
        mismatches = []
        seen: set[tuple[str, str]] = set()
        for bal in balances:
            src = str(bal.get("source_company_id") or "")
            tgt = str(bal.get("target_company_id") or "")
            if not src or not tgt:
                continue
            key = tuple(sorted([src, tgt]))
            if key in seen:
                continue
            seen.add(key)
            amt = float(bal.get("amount") or 0)
            reverse = next(
                (
                    b
                    for b in balances
                    if str(b.get("source_company_id")) == tgt
                    and str(b.get("target_company_id")) == src
                ),
                None,
            )
            rev_amt = float((reverse or {}).get("amount") or 0)
            if abs(amt + rev_amt) > 0.01:
                mismatches.append(
                    {
                        "source_company_id": src,
                        "target_company_id": tgt,
                        "amount": amt,
                        "reverse_amount": rev_amt,
                        "gap": round(amt + rev_amt, 2),
                    }
                )
        return mismatches


intercompany_service = IntercompanyService()
