from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import intelligence_registry
from app.modules.erp.tax.engine.reconciliation_engine import match_2b_row
from app.modules.erp.tax.events.tax_events import emit_gst_mismatch_detected
from app.modules.erp.tax.repositories.gst_repository import gst_transaction_repository
from app.modules.erp.tax.repositories.return_repository import gst_reconciliation_repository, gstr2b_repository


class GstReconciliationService:
    def import_2b(self, org_id: str, *, return_period: str, rows: list[dict]) -> dict:
        count = gstr2b_repository.bulk_insert(org_id, return_period=return_period, rows=rows)
        return {"imported": count, "return_period": return_period}

    def run_reconciliation(self, org_id: str, *, return_period: str) -> list[dict]:
        purchases = gst_transaction_repository.list(org_id, return_period=return_period, gst_type="purchase")
        gstr2b_rows = gstr2b_repository.list(org_id, return_period=return_period)
        created = []
        matched_2b_ids: set[str] = set()
        for tx in purchases:
            best = None
            best_row = None
            for g2b in gstr2b_rows:
                if str(g2b.get("id")) in matched_2b_ids:
                    continue
                scored = match_2b_row(tx, g2b)
                if not best or scored["confidence_score"] > best["confidence_score"]:
                    best = scored
                    best_row = g2b
            if best and best_row:
                matched_2b_ids.add(str(best_row.get("id")))
                row = gst_reconciliation_repository.create(
                    org_id,
                    gst_transaction_id=str(tx.get("id")),
                    gstr2b_import_id=str(best_row.get("id")),
                    return_period=return_period,
                    match_status=best["match_status"],
                    confidence_score=best["confidence_score"],
                    metadata={"factors": best.get("factors")},
                )
                created.append(row)
                if best["match_status"] == "mismatch":
                    flags = intelligence_registry.tax().detect_mismatches(tx, best_row)
                    emit_gst_mismatch_detected(org_id, reconciliation_id=str(row.get("id")), summary=", ".join(flags.get("flags") or []))
                    try:
                        from app.modules.platform.governance.services.compliance_service import compliance_service

                        compliance_service.track_gst_itc_mismatch(org_id, return_id=return_period, delta_amount=flags.get("tax_delta", 0))
                    except Exception:
                        pass
        return created

    def list_reconciliations(self, org_id: str, *, return_period: str | None = None, match_status: str | None = None) -> list[dict]:
        return gst_reconciliation_repository.list(org_id, return_period=return_period, match_status=match_status)

    def resolve(self, org_id: str, *, reconciliation_id: str, actor_id: str) -> dict:
        result = gst_reconciliation_repository.resolve(org_id, reconciliation_id=reconciliation_id, status="resolved")
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id,
                action="gst.reconciliation.resolved",
                object_ref=f"erp:gst_reconciliation:{reconciliation_id}",
                payload={"reconciliation_id": reconciliation_id},
                entity_type="gst_reconciliation",
                entity_id=reconciliation_id,
                source_service="erp.tax",
            )
        except Exception:
            pass
        return result


gst_reconciliation_service = GstReconciliationService()
