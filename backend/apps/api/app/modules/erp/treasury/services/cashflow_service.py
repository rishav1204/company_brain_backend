from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.ports.intelligence_registry import intelligence_registry


class CashflowService:
    def build_forecast(self, org_id: str, *, horizon_days: int = 30) -> dict:
        inflows = self._collect_inflows(org_id)
        outflows = self._collect_outflows(org_id)
        return intelligence_registry.treasury().forecast_cashflow(
            inflows=inflows,
            outflows=outflows,
            horizon_days=horizon_days,
        )

    def _collect_inflows(self, org_id: str) -> list[dict]:
        items: list[dict] = []
        try:
            from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

            for inv in ar_invoice_repository.list_outstanding(org_id):
                outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
                if outstanding > 0:
                    items.append({"date": inv.get("due_date"), "amount": outstanding, "source": "ar"})
        except Exception:
            pass
        try:
            from app.modules.erp.treasury.repositories.bank_transaction_repository import bank_transaction_repository

            for tx in bank_transaction_repository.list(
                org_id, reconciliation_status="matched", limit=200
            ):
                if str(tx.get("transaction_type")) == "credit":
                    items.append({
                        "date": tx.get("transaction_date"),
                        "amount": float(tx.get("amount") or 0),
                        "source": "bank_credit",
                    })
        except Exception:
            pass
        items.extend(self._org_forecast_inflows(org_id))
        return items

    def _collect_outflows(self, org_id: str) -> list[dict]:
        items: list[dict] = []
        try:
            from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

            for inv in invoice_repository.list_outstanding(org_id):
                outstanding = float(inv.get("outstanding") or inv.get("total_amount") or 0) - float(
                    inv.get("paid_amount") or 0
                )
                if outstanding > 0:
                    items.append({"date": inv.get("due_date"), "amount": outstanding, "source": "ap"})
        except Exception:
            pass
        try:
            from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

            for p in payment_repository.list(org_id, status="scheduled"):
                items.append({"date": p.get("payment_date"), "amount": float(p.get("amount") or 0), "source": "ap_payment"})
        except Exception:
            pass
        try:
            from app.modules.erp.treasury.repositories.payment_request_repository import payment_request_repository

            for pr in payment_request_repository.list_by_types(
                org_id, payment_types=["salary", "tax_payment"]
            ):
                items.append({
                    "date": pr.get("scheduled_date"),
                    "amount": float(pr.get("amount") or 0),
                    "source": str(pr.get("payment_type")),
                })
            through = (date.today() + timedelta(days=90)).isoformat()
            for pr in payment_request_repository.list(org_id, status="approved"):
                if pr.get("scheduled_date") and str(pr["scheduled_date"]) <= through:
                    items.append({
                        "date": pr.get("scheduled_date"),
                        "amount": float(pr.get("amount") or 0),
                        "source": "treasury_payment",
                    })
        except Exception:
            pass
        items.extend(self._org_forecast_outflows(org_id))
        return items

    def _org_forecast_hooks(self, org_id: str) -> dict:
        try:
            from app.modules.core.iam.repositories.organization_repository import organization_repository

            org = organization_repository.get_organization(org_id) or {}
            meta = org.get("metadata") if isinstance(org.get("metadata"), dict) else {}
            forecast = meta.get("treasury_forecast")
            return forecast if isinstance(forecast, dict) else {}
        except Exception:
            return {}

    def _org_forecast_inflows(self, org_id: str) -> list[dict]:
        forecast = self._org_forecast_hooks(org_id)
        items: list[dict] = []
        for entry in forecast.get("monthly_inflows") or []:
            if isinstance(entry, dict) and entry.get("amount"):
                items.append({
                    "date": entry.get("date") or date.today().isoformat(),
                    "amount": float(entry["amount"]),
                    "source": entry.get("source") or "forecast",
                })
        return items

    def _org_forecast_outflows(self, org_id: str) -> list[dict]:
        forecast = self._org_forecast_hooks(org_id)
        items: list[dict] = []
        for entry in forecast.get("monthly_outflows") or []:
            if isinstance(entry, dict) and entry.get("amount"):
                items.append({
                    "date": entry.get("date") or date.today().isoformat(),
                    "amount": float(entry["amount"]),
                    "source": entry.get("source") or "forecast",
                })
        return items


cashflow_service = CashflowService()
