from __future__ import annotations

import time
import uuid

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
from app.modules.erp.gl.repositories.ledger_repository import ledger_repository
from app.modules.erp.gl.services.fiscal_period_service import fiscal_period_service
from app.modules.erp.gl.validators.double_entry_validator import validate_double_entry
from app.services.db import get_db_conn, set_rls_org
from app.services.metrics import metrics_store


class PostingService:
    def post(self, org_id: str, *, posted_by: str | None, posting_date: str, lines: list[dict], company_id: str | None = None) -> dict:
        started = time.time()
        if not lines:
            raise ValueError("No posting lines")

        try:
            # Validate double-entry first (fast fail)
            total_debit, total_credit = validate_double_entry(lines)

            # Fiscal period resolution (must be open)
            period = fiscal_period_service.resolve_open_period(org_id, posting_date=posting_date, company_id=company_id)
            fiscal_period_id = str(period["id"])

            # Validate accounts exist/active/postable
            # (Batch fetch optimization can come later.)
            group_cache: dict[str, dict] = {}
            for l in lines:
                aid = str(l.get("account_id") or "")
                if not aid:
                    raise ValueError("Missing account_id")
                acc = account_repository.get(org_id, account_id=aid)
                if not acc or not bool(acc.get("is_active")):
                    raise ValueError("Account not active")
                if not bool(acc.get("is_postable")):
                    raise ValueError("Account is not postable")
                gid = str(acc.get("group_id") or "")
                if gid and gid not in group_cache:
                    g = account_group_repository.get(org_id, group_id=gid)
                    group_cache[gid] = g or {}

            batch_number = "LB-" + uuid.uuid4().hex[:12].upper()

            # Atomic posting: batch + entries + balance projection within one DB transaction
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)

                batch = ledger_repository.create_batch(conn, org_id, batch_number=batch_number, posted_by=posted_by)
                batch_id = str(batch["id"])

                ledger_repository.insert_entries(
                    conn,
                    org_id,
                    batch_id=batch_id,
                    fiscal_period_id=fiscal_period_id,
                    posting_date=posting_date,
                    lines=lines,
                )

                totals: dict[str, tuple[float, float]] = {}
                for l in lines:
                    aid = str(l["account_id"])
                    d = float(l.get("debit_amount") or 0)
                    c = float(l.get("credit_amount") or 0)
                    prev = totals.get(aid, (0.0, 0.0))
                    totals[aid] = (prev[0] + d, prev[1] + c)
                for aid, (d, c) in totals.items():
                    acc = account_repository.get(org_id, account_id=aid) or {}
                    g = group_cache.get(str(acc.get("group_id") or ""), {}) or {}
                    nature = str(g.get("nature") or "debit").lower()
                    closing = (d - c) if nature == "debit" else (c - d)
                    ledger_repository.upsert_balance(
                        conn,
                        org_id,
                        account_id=aid,
                        fiscal_period_id=fiscal_period_id,
                        debit_delta=d,
                        credit_delta=c,
                        closing_balance=closing,
                    )

        # Emit events + audit logs best-effort
        try:
            from app.modules.platform.events.services.event_service import platform_event_service

            platform_event_service.publish(
                event_type="erp.ledger.posted",
                org_id=org_id,
                source="erp.gl",
                entity_type="ledger_batch",
                entity_id=batch_id,
                payload={"batch_id": batch_id, "batch_number": batch_number, "posting_date": posting_date},
            )
        except Exception:
            pass
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id=posted_by or "erp.gl",
                action="erp.ledger.posted",
                object_ref=f"erp:ledger_batch:{batch_id}",
                payload={"batch_number": batch_number, "total_debit": total_debit, "total_credit": total_credit},
                entity_type="ledger_batch",
                entity_id=batch_id,
                source_service="erp.gl",
            )
        except Exception:
            pass

            metrics_store.incr_gl_posting()
            metrics_store.observe_gl_posting_latency_ms(int((time.time() - started) * 1000))
            return {"batch": batch, "totals": {"debit": total_debit, "credit": total_credit}, "fiscal_period_id": fiscal_period_id}
        except Exception:
            metrics_store.incr_gl_posting_failure()
            metrics_store.observe_gl_posting_latency_ms(int((time.time() - started) * 1000))
            raise


posting_service = PostingService()

