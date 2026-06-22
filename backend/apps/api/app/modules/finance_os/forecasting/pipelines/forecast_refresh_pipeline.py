from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository as ap_invoice_repo
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.compliance.repositories.compliance_repository import compliance_obligation_repository
from app.modules.erp.treasury.repositories.cash_position_repository import cash_position_repository
from app.modules.finance_os.forecasting.engine.cash_forecast_engine import forecast_cash
from app.modules.finance_os.forecasting.engine.collections_engine import forecast_collections
from app.modules.finance_os.forecasting.engine.expense_engine import forecast_expenses
from app.modules.finance_os.forecasting.engine.tax_engine import forecast_tax
from app.modules.finance_os.forecasting.engine.working_capital_engine import forecast_working_capital
from app.modules.finance_os.forecasting.engine.forecast_scoring_engine import score_confidence
from app.modules.finance_os.forecasting.repositories.forecast_repository import forecast_repository
from app.modules.finance_os.forecasting.repositories.explanation_repository import explanation_repository
from app.modules.finance_os.forecasting.services.forecast_explanation_service import explain_forecast
from app.modules.finance_os.forecasting.events.forecast_events import (
    emit_forecast_generated,
)
from app.modules.platform.billing.billing_hooks import billing_ai_operation


SUPPORTED_HORIZONS = [7, 30, 60, 90, 180, 365]


def _as_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(str(value)[:10])
    return date.today()


def _sum_outstanding(items: list[dict]) -> float:
    total = 0.0
    for it in items or []:
        try:
            total += float(it.get("outstanding") or 0.0)
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def run_refresh(org_id: str, *, as_of_date: str | None = None, horizons: list[int] | None = None, trace_id: str | None = None) -> dict:
    with billing_ai_operation(org_id, feature="forecasting", operation_code="forecast_generation"):
        return _run_refresh_inner(org_id, as_of_date=as_of_date, horizons=horizons, trace_id=trace_id)


def _run_refresh_inner(org_id: str, *, as_of_date: str | None = None, horizons: list[int] | None = None, trace_id: str | None = None) -> dict:
    if not forecast_repository.schema_ready():
        return {"status": "skipped", "reason": "schema_not_ready"}

    as_of = _as_date(as_of_date)
    horizons = [int(h) for h in (horizons or SUPPORTED_HORIZONS) if int(h) in SUPPORTED_HORIZONS]
    if not horizons:
        horizons = SUPPORTED_HORIZONS

    outstanding_ar = ar_invoice_repository.list_outstanding(org_id)
    outstanding_ap = ap_invoice_repo.list_outstanding(org_id)
    obligations = compliance_obligation_repository.list(
        org_id,
        from_date=as_of.isoformat(),
        to_date=(as_of + timedelta(days=max(horizons))).isoformat(),
        limit=500,
    )

    # Cash: sum latest closing across accounts (simple proxy)
    cash_positions = cash_position_repository.list_history(org_id, limit=30)
    starting_cash = 0.0
    for row in cash_positions[:10]:
        try:
            starting_cash += float(row.get("closing_balance") or 0.0)
        except (TypeError, ValueError):
            continue
    starting_cash = round(starting_cash, 2)

    result: dict = {"status": "ok", "as_of_date": as_of.isoformat(), "horizons": horizons, "generated": {}}
    for h in horizons:
        # collections/payments/tax for cash model
        collections = forecast_collections(as_of=as_of, horizon_days=h, outstanding_ar=outstanding_ar, customer_memory={})
        payments = forecast_expenses(as_of=as_of, horizon_days=h, historical_daily_expense=[])  # placeholder: AP schedule v1
        taxes = forecast_tax(as_of=as_of, horizon_days=h, upcoming_obligations=obligations)
        cash_rows = forecast_cash(
            as_of=as_of,
            horizon_days=h,
            starting_cash=starting_cash,
            expected_collections=collections,
            expected_payments=payments,
            expected_tax=taxes,
        )

        wc_rows = forecast_working_capital(as_of=as_of, horizon_days=h, outstanding_ar=outstanding_ar, outstanding_ap=outstanding_ap)
        exp_rows = forecast_expenses(as_of=as_of, horizon_days=h, historical_daily_expense=[])

        mem_hits = 0
        graph_evidence = 0
        conf_score, conf_band = score_confidence(data_quality=0.7 if cash_positions else 0.4, memory_hits=mem_hits, graph_evidence=graph_evidence, history_days=30)

        inputs_cash = {
            "starting_cash": starting_cash,
            "ar_outstanding_total": _sum_outstanding(outstanding_ar),
            "ap_outstanding_total": _sum_outstanding(outstanding_ap),
            "min_cash": min(float(r["forecast_value"]) for r in cash_rows) if cash_rows else starting_cash,
        }

        def _persist_series(ftype: str, rows: list[dict], inputs: dict) -> list[str]:
            ids: list[str] = []
            for r in rows:
                persisted = forecast_repository.upsert(
                    org_id,
                    forecast_type=ftype,
                    horizon_days=h,
                    as_of_date=as_of.isoformat(),
                    forecast_date=str(r["forecast_date"])[:10],
                    forecast_value=float(r["forecast_value"]),
                    confidence_score=conf_score,
                    confidence_band=conf_band,
                    inputs=inputs,
                )
                if persisted.get("id"):
                    ids.append(str(persisted["id"]))
            return ids

        cash_ids = _persist_series("cash", cash_rows, inputs_cash)
        exp_ids = _persist_series("expenses", exp_rows, {"baseline": exp_rows[0]["forecast_value"] if exp_rows else 0})
        wc_ids = _persist_series("working_capital", wc_rows, {"ar_outstanding_total": _sum_outstanding(outstanding_ar), "ap_outstanding_total": _sum_outstanding(outstanding_ap)})

        if cash_ids:
            explanation = explain_forecast(org_id, forecast_type="cash", horizon_days=h, rows=cash_rows, inputs=inputs_cash, memory_count=mem_hits, graph_count=graph_evidence)
            explanation_repository.create(org_id, forecast_id=cash_ids[0], explanation=str(explanation.get("answer") or ""), evidence=explanation.get("sources") or {})

        emit_forecast_generated(org_id, forecast_type="cash", horizon_days=h, as_of_date=as_of.isoformat(), confidence=conf_score, trace_id=trace_id)
        result["generated"][str(h)] = {"cash": len(cash_ids), "expenses": len(exp_ids), "working_capital": len(wc_ids)}

    return result

