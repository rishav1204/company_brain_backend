from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.tax.engine.filing_engine import build_gstr1_payload, build_gstr3b_payload, build_gstr9_payload
from app.modules.erp.tax.repositories.gst_repository import gst_transaction_repository
from app.modules.erp.tax.repositories.itc_repository import itc_ledger_repository
from app.modules.erp.tax.repositories.return_repository import gst_return_repository
from app.modules.platform.events.events.erp_events import emit_gst_return_generated


class GstReturnService:
    def generate_return(self, org_id: str, *, return_type: str, return_period: str) -> dict:
        txs = gst_transaction_repository.list(org_id, return_period=return_period)
        if return_type == "GSTR-1":
            payload = build_gstr1_payload(txs, return_period=return_period)
        elif return_type == "GSTR-3B":
            itc_claimed = itc_ledger_repository.sum_claimed(org_id, return_period=return_period)
            payload = build_gstr3b_payload(txs, return_period=return_period, itc_claimed=itc_claimed)
        elif return_type == "GSTR-9":
            fy = return_period if len(return_period) == 4 else return_period[:4]
            txs = gst_transaction_repository.list_for_financial_year(org_id, financial_year=fy)
            payload = build_gstr9_payload(txs, financial_year=fy)
        else:
            raise ValueError(f"Unsupported return type: {return_type}")
        row = gst_return_repository.create(org_id, return_type=return_type, return_period=return_period, payload=payload)
        emit_gst_return_generated(org_id, return_id=str(row["id"]), period=return_period)
        return row

    def list_returns(self, org_id: str, *, return_type: str | None = None) -> list[dict]:
        return gst_return_repository.list(org_id, return_type=return_type)

    def get_return(self, org_id: str, *, return_id: str) -> dict:
        row = gst_return_repository.get(org_id, return_id=return_id)
        if not row:
            raise ValueError("GST return not found")
        return row

    def submit_for_approval(self, org_id: str, *, return_id: str, started_by: str | None) -> dict:
        row = self.get_return(org_id, return_id=return_id)
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "gst_return",
                    "entity_id": return_id,
                    "workflow_key": "GST_FILING",
                    "started_by": started_by,
                    "metadata": {"return_type": row.get("return_type"), "return_period": row.get("return_period")},
                },
            )
        except Exception:
            gst_return_repository.set_status(org_id, return_id=return_id, status="approved", workflow_approved=True)
        gst_return_repository.set_status(org_id, return_id=return_id, status="pending_approval")
        return gst_return_repository.get(org_id, return_id=return_id) or {}

    def mark_workflow_approved(self, org_id: str, *, return_id: str) -> dict:
        return gst_return_repository.set_status(org_id, return_id=return_id, status="approved", workflow_approved=True)

    def file_return(self, org_id: str, *, return_id: str, filed_by: str) -> dict:
        row = self.get_return(org_id, return_id=return_id)
        if not row.get("workflow_approved") and str(row.get("status")) != "approved":
            raise ValueError("GST return workflow approval required before filing")
        from app.modules.platform.integrations.connectors.gst.gst_connector_resolver import resolve_gst_filing_connector

        connector = resolve_gst_filing_connector()
        if not connector:
            raise ValueError("GST connector not available")
        result = connector.submit_return(
            idempotency_key=f"{org_id}:{return_id}",
            payload={"return_type": row.get("return_type"), "return_period": row.get("return_period"), "data": row.get("payload")},
        )
        filed = gst_return_repository.set_status(
            org_id,
            return_id=return_id,
            status="filed",
            filed_at=datetime.now(timezone.utc).isoformat(),
            filed_by=filed_by,
        )
        emit_gst_return_generated(org_id, return_id=return_id, period=str(row.get("return_period")))
        try:
            from app.modules.erp.tax.events.tax_events import emit_compliance_alert

            emit_compliance_alert(org_id, alert_type="gst.return.filed", summary=f"GST return filed for {row.get('return_period')}")
        except Exception:
            pass
        try:
            from app.modules.platform.governance.services.compliance_service import compliance_service

            compliance_service.track_gst_filing(org_id, return_id=return_id, period=str(row.get("return_period")), status="filed")
        except Exception:
            pass
        self._audit(org_id, return_id=return_id, action="tax.gst.return.filed", actor_id=filed_by)
        try:
            from app.modules.erp.compliance.services.obligation_service import obligation_service

            code_map = {"GSTR-1": "GST_GSTR1", "GSTR-3B": "GST_GSTR3B", "GSTR-9": "GST_GSTR3B"}
            obligation_service.complete_by_source(
                org_id,
                compliance_code=code_map.get(str(row.get("return_type")), "GST_GSTR3B"),
                return_period=str(row.get("return_period") or "")[:7] or None,
                source_id=return_id,
            )
        except Exception:
            pass
        return {"return": filed, "connector_result": {"status": result.status, "return_period": result.return_period}}

    def _audit(self, org_id: str, *, return_id: str, action: str, actor_id: str) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id, actor_type="user", actor_id=actor_id, action=action,
                object_ref=f"erp:gst_return:{return_id}", entity_type="gst_return", entity_id=return_id,
                source_service="erp.tax",
            )
        except Exception:
            pass


gst_return_service = GstReturnService()
