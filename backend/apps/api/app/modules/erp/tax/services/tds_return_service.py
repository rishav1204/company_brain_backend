from __future__ import annotations

from app.modules.erp.tax.repositories.compliance_repository import tds_transaction_repository
from app.modules.erp.tax.repositories.tcs_transaction_repository import tcs_transaction_repository
from app.modules.erp.tax.repositories.tds_return_repository import tds_return_repository
from app.modules.erp.tax.events.tax_events import emit_compliance_alert


def _build_return_payload(
    *,
    form_type: str,
    return_period: str,
    txs: list[dict],
    tax_field: str = "tds_amount",
) -> dict:
    by_section: dict[str, dict] = {}
    for tx in txs:
        sec = str(tx.get("section_code") or "194C")
        bucket = by_section.setdefault(sec, {"section_code": sec, "gross_total": 0.0, "tax_total": 0.0, "count": 0})
        bucket["gross_total"] = round(bucket["gross_total"] + float(tx.get("gross_amount") or 0), 2)
        bucket["tax_total"] = round(bucket["tax_total"] + float(tx.get(tax_field) or 0), 2)
        bucket["count"] += 1
    return {
        "form_type": form_type,
        "return_period": return_period,
        "sections": list(by_section.values()),
        "summary": {
            "total_tax": round(sum(s["tax_total"] for s in by_section.values()), 2),
            "transaction_count": len(txs),
        },
    }


class TdsReturnService:
    def generate_return(self, org_id: str, *, return_period: str, form_type: str = "26Q") -> dict:
        form = form_type.upper()
        if form in {"27EQ", "TCS"}:
            txs = [
                t for t in tcs_transaction_repository.list(org_id, limit=500)
                if str(t.get("return_period") or "") == return_period or not t.get("return_period")
            ]
            payload = _build_return_payload(form_type="27EQ", return_period=return_period, txs=txs, tax_field="tcs_amount")
        elif form == "24Q":
            from app.modules.erp.payroll.repositories.salary_run_repository import salary_run_repository
            from app.modules.erp.tax.services.payroll_tds_service import payroll_tds_service

            payroll_tds_service.sync_all(org_id, return_period=return_period)
            txs = [
                t for t in tds_transaction_repository.list(org_id, limit=5000)
                if str(t.get("return_period") or "") == return_period or not t.get("return_period")
            ]
            salary_txs = [
                t for t in txs
                if str(t.get("section_code") or "").upper() in {"192", "192A"}
                or str(t.get("source_type") or "").lower() in {"payroll", "salary", "payroll_payment", "payroll_salary_run"}
            ]
            payload = _build_return_payload(form_type="24Q", return_period=return_period, txs=salary_txs)
            salary_runs = salary_run_repository.list(org_id, return_period=return_period, limit=5000)
            payload["employees"] = [
                {
                    "employee_id": r.get("employee_id"),
                    "employee_code": r.get("employee_code"),
                    "pan": r.get("pan"),
                    "name": r.get("employee_name"),
                    "gross_salary": float(r.get("gross_salary") or 0),
                    "tds_amount": float(r.get("tds_amount") or 0),
                    "tds_section": r.get("tds_section") or "192",
                    "payment_date": r.get("payment_date"),
                    "salary_run_id": r.get("id"),
                }
                for r in salary_runs
            ]
            payload["export_format"] = "24Q_JSON"
            payload["summary"]["employee_count"] = len(payload["employees"])
            if not salary_txs and not payload["employees"]:
                payload["summary"]["note"] = "No salary TDS transactions for period; run payroll salary-runs or sync"
        elif form == "27Q":
            txs = [
                t for t in tds_transaction_repository.list(org_id, limit=500)
                if str(t.get("return_period") or "") == return_period or not t.get("return_period")
            ]
            payload = _build_return_payload(form_type="27Q", return_period=return_period, txs=txs)
        else:
            txs = [
                t for t in tds_transaction_repository.list(org_id, limit=500)
                if str(t.get("return_period") or "") == return_period or not t.get("return_period")
            ]
            payload = _build_return_payload(form_type="26Q", return_period=return_period, txs=txs)
            payload["summary"]["total_tds"] = payload["summary"].pop("total_tax")

        row = tds_return_repository.create(org_id, return_period=return_period, form_type=form, payload=payload)
        emit_compliance_alert(org_id, alert_type="tds.return.generated", summary=f"TDS {form} generated for {return_period}")
        return row

    def list_returns(self, org_id: str) -> list[dict]:
        return tds_return_repository.list(org_id)

    def get_return(self, org_id: str, *, return_id: str) -> dict:
        row = tds_return_repository.get(org_id, return_id=return_id)
        if not row:
            raise ValueError("TDS return not found")
        return row

    def submit_for_approval(self, org_id: str, *, return_id: str, started_by: str | None) -> dict:
        row = self.get_return(org_id, return_id=return_id)
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "tds_return",
                    "entity_id": return_id,
                    "workflow_key": "TDS_FILING",
                    "started_by": started_by,
                    "metadata": {"return_period": row.get("return_period"), "form_type": row.get("form_type")},
                },
            )
        except Exception:
            tds_return_repository.set_status(org_id, return_id=return_id, status="approved", workflow_approved=True)
        tds_return_repository.set_status(org_id, return_id=return_id, status="pending_approval")
        return tds_return_repository.get(org_id, return_id=return_id) or {}

    def mark_workflow_approved(self, org_id: str, *, return_id: str) -> dict:
        return tds_return_repository.set_status(org_id, return_id=return_id, status="approved", workflow_approved=True)

    def generate_fvu(self, org_id: str, *, return_id: str) -> dict:
        row = self.get_return(org_id, return_id=return_id)
        from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import resolve_tds_filing_connector

        connector = resolve_tds_filing_connector()
        if not connector or not hasattr(connector, "generate_fvu"):
            raise ValueError("TDS FVU connector not available")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        fvu = connector.generate_fvu(
            payload={
                "form_type": row.get("form_type"),
                "return_period": row.get("return_period"),
                "data": payload,
            }
        )
        return {"return_id": return_id, **fvu}

    def file_return(self, org_id: str, *, return_id: str, filed_by: str) -> dict:
        row = self.get_return(org_id, return_id=return_id)
        if not row.get("workflow_approved") and str(row.get("status")) != "approved":
            raise ValueError("TDS return workflow approval required before filing")
        from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import resolve_tds_filing_connector

        connector = resolve_tds_filing_connector()
        if not connector:
            raise ValueError("TDS filing connector not available")
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        result = connector.submit_return(
            idempotency_key=f"{org_id}:{return_id}",
            payload={
                "form_type": row.get("form_type"),
                "return_period": row.get("return_period"),
                "data": payload,
            },
        )
        filed = tds_return_repository.set_status(org_id, return_id=return_id, status="filed", filed_by=filed_by)
        emit_compliance_alert(
            org_id,
            alert_type="tds.return.filed",
            summary=f"TDS {row.get('form_type')} filed for {row.get('return_period')} — ack {result.acknowledgment_no}",
        )
        try:
            from app.modules.erp.compliance.services.obligation_service import obligation_service

            form = str(row.get("form_type") or "26Q").upper()
            code = "TDS_27Q" if form in {"27Q", "27EQ", "TCS"} else "TDS_26Q"
            obligation_service.complete_by_source(
                org_id,
                compliance_code=code,
                return_period=str(row.get("return_period") or "")[:7] or None,
                source_id=return_id,
            )
        except Exception:
            pass
        return {**filed, "acknowledgment_no": result.acknowledgment_no, "filed_at": result.filed_at}


tds_return_service = TdsReturnService()
