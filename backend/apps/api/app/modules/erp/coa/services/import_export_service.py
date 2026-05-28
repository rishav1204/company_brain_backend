from __future__ import annotations

from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.services.account_validation_service import account_validation_service


class ImportExportService:
    def template(self) -> dict:
        return {
            "format": "json_rows",
            "fields": [
                "group_code",
                "group_name",
                "group_type",
                "nature",
                "parent_group_code",
                "account_code",
                "account_name",
                "account_type",
                "parent_account_code",
                "is_postable",
                "currency_code",
            ],
            "example": [
                {
                    "group_code": "ASSET_CURRENT",
                    "group_name": "Current Assets",
                    "group_type": "asset",
                    "nature": "debit",
                    "parent_group_code": None,
                    "account_code": "1000",
                    "account_name": "Cash",
                    "account_type": "cash",
                    "parent_account_code": None,
                    "is_postable": True,
                    "currency_code": "INR",
                }
            ],
        }

    def import_coa(self, org_id: str, *, rows: list) -> dict:
        if not rows:
            return {"imported": 0}

        # Validate duplicates in payload
        group_codes = [str(r.group_code) for r in rows]
        account_codes = [str(r.account_code) for r in rows]
        if len(set(group_codes)) != len(group_codes):
            raise ValueError("Duplicate group_code in import payload")
        if len(set(account_codes)) != len(account_codes):
            raise ValueError("Duplicate account_code in import payload")

        # Validate group rules + build parent links by code
        parent_by_group_code = {str(r.group_code): (str(r.parent_group_code) if r.parent_group_code else None) for r in rows}
        for gc, pgc in parent_by_group_code.items():
            if pgc and pgc not in parent_by_group_code:
                raise ValueError(f"parent_group_code not found: {pgc}")
            # loop check by code graph
            seen = {gc}
            cur = pgc
            while cur:
                if cur in seen:
                    raise ValueError("Group hierarchy loop in import payload")
                seen.add(cur)
                cur = parent_by_group_code.get(cur)

        # Create groups in topological-ish order (simple repeated passes)
        created_groups: dict[str, str] = {}
        pending = set(parent_by_group_code.keys())
        for _ in range(len(pending) + 2):
            progressed = False
            for gc in list(pending):
                pgc = parent_by_group_code.get(gc)
                if pgc and pgc not in created_groups:
                    continue
                r = next(x for x in rows if str(x.group_code) == gc)
                account_validation_service.validate_group(group_type=str(r.group_type), nature=str(r.nature))
                row = account_group_repository.create(
                    org_id,
                    group_name=str(r.group_name),
                    group_code=str(r.group_code),
                    group_type=str(r.group_type),
                    nature=str(r.nature),
                    parent_group_id=created_groups.get(pgc) if pgc else None,
                    company_id=None,
                )
                created_groups[gc] = str(row["id"])
                pending.remove(gc)
                progressed = True
            if not pending:
                break
            if not progressed:
                raise ValueError("Unable to resolve group parents in import")

        # Accounts parent by code (must reference within import payload)
        parent_by_account_code = {
            str(r.account_code): (str(r.parent_account_code) if r.parent_account_code else None) for r in rows
        }
        for ac, pac in parent_by_account_code.items():
            if pac and pac not in parent_by_account_code:
                raise ValueError(f"parent_account_code not found: {pac}")
            seen = {ac}
            cur = pac
            while cur:
                if cur in seen:
                    raise ValueError("Account hierarchy loop in import payload")
                seen.add(cur)
                cur = parent_by_account_code.get(cur)

        created_accounts: dict[str, str] = {}
        pending_accounts = set(parent_by_account_code.keys())
        for _ in range(len(pending_accounts) + 2):
            progressed = False
            for ac in list(pending_accounts):
                pac = parent_by_account_code.get(ac)
                if pac and pac not in created_accounts:
                    continue
                r = next(x for x in rows if str(x.account_code) == ac)
                account_validation_service.validate_account(
                    account_type=str(r.account_type),
                    is_postable=bool(r.is_postable),
                    parent_account_id=created_accounts.get(pac) if pac else None,
                )
                row = account_repository.create(
                    org_id,
                    account_code=str(r.account_code),
                    account_name=str(r.account_name),
                    account_type=str(r.account_type),
                    group_id=created_groups[str(r.group_code)],
                    parent_account_id=created_accounts.get(pac) if pac else None,
                    is_postable=bool(r.is_postable),
                    currency_code=str(r.currency_code or "INR"),
                    company_id=None,
                )
                created_accounts[ac] = str(row["id"])
                pending_accounts.remove(ac)
                progressed = True
            if not pending_accounts:
                break
            if not progressed:
                raise ValueError("Unable to resolve account parents in import")

        # Emit audit/event marker (best-effort)
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.services.metrics import metrics_store

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="erp.coa",
                action="erp.coa.imported",
                object_ref="erp:coa",
                payload={"groups": len(created_groups), "accounts": len(created_accounts)},
                entity_type="coa",
                entity_id="coa",
                source_service="erp.coa",
            )
            metrics_store.incr_governance_webhook_delivery()  # reuse counter best-effort (until dedicated metric)
        except Exception:
            pass
        return {"imported_groups": len(created_groups), "imported_accounts": len(created_accounts)}


import_export_service = ImportExportService()

