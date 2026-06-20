from __future__ import annotations

from app.modules.finance_os.invoice_ai.ai.gst_predictor import predict_gst_code
from app.modules.finance_os.invoice_ai.ai.ledger_predictor import suggest_from_patterns
from app.modules.finance_os.invoice_ai.repositories.prediction_repository import PredictionRepository
from app.modules.finance_os.invoice_ai.retrieval.accounting_patterns import get_accounting_patterns
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.services.db import get_db_conn, set_rls_org

prediction_repository = PredictionRepository()


class LedgerSuggestionService:
    def _vendor_history_account(self, org_id: str, vendor_id: str | None) -> str | None:
        if not vendor_id:
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT a.code
                    FROM erp.ap_invoice_lines l
                    JOIN erp.ap_invoices i ON i.id = l.invoice_id
                    JOIN erp.coa_accounts a ON a.id = l.account_id
                    WHERE i.org_id = %s::uuid AND i.vendor_id = %s::uuid
                      AND l.line_type = 'expense'
                    GROUP BY a.code
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                    """,
                    (org_id, vendor_id),
                )
                row = cur.fetchone()
                return str(row["code"]) if row else None

    def predict(self, org_id: str, *, extraction: dict) -> list[dict]:
        vendor_name = str(extraction.get("vendor_name") or "")
        vendor_id = extraction.get("vendor_id")
        if not vendor_id and extraction.get("vendor_gstin"):
            v = vendor_repository.find_by_gstin(org_id, gstin=str(extraction["vendor_gstin"]))
            vendor_id = v.get("id") if v else None

        patterns = get_accounting_patterns(org_id, description=vendor_name, vendor_name=vendor_name)
        history_code = self._vendor_history_account(org_id, str(vendor_id) if vendor_id else None)
        suggestion = suggest_from_patterns(patterns, vendor_account=history_code)

        predictions: list[dict] = []
        if suggestion:
            conf = float(suggestion.get("confidence_score") or 0)
            conf_pct = conf * 100 if conf <= 1 else conf
            predictions.append(
                prediction_repository.create(
                    org_id,
                    data={
                        "extraction_id": extraction["id"],
                        "prediction_type": "ledger",
                        "suggested_account_id": suggestion.get("suggested_account_id"),
                        "confidence_score": conf_pct,
                        "metadata": {
                            "account_code": suggestion.get("account_code"),
                            "source": suggestion.get("source"),
                        },
                    },
                )
            )

        gst = predict_gst_code(
            vendor_gstin=extraction.get("vendor_gstin"),
            taxable_amount=float(extraction.get("taxable_amount") or 0),
            gst_amount=float(extraction.get("gst_amount") or 0),
        )
        gst_conf = float(gst.get("confidence_score") or 0)
        gst_pct = gst_conf * 100 if gst_conf <= 1 else gst_conf
        predictions.append(
            prediction_repository.create(
                org_id,
                data={
                    "extraction_id": extraction["id"],
                    "prediction_type": "gst",
                    "suggested_gst_code": gst.get("suggested_gst_code"),
                    "confidence_score": gst_pct,
                    "metadata": gst,
                },
            )
        )
        return predictions


ledger_suggestion_service = LedgerSuggestionService()
