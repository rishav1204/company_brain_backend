"""ERP-owned read dispatch — sole allowlisted importlib surface for Finance OS tools."""

from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable

# Populated from historical catalog_read targets + FOS analytics/forecast needs.
_READ_ALLOWLIST: set[tuple[str, str, str]] = set()
_HANDLER_CACHE: dict[tuple[str, str, str], Callable[..., Any]] = {}


def register_read_target(module: str, service: str, fn: str) -> None:
    if not module.startswith("app.modules.erp."):
        raise ValueError(f"read target must be under erp: {module}")
    if module.startswith("app.modules.erp.query_services"):
        # query services may re-export internal targets only via this API
        pass
    _READ_ALLOWLIST.add((module, service, fn))


def register_read_targets(items: list[tuple[str, str, str]]) -> None:
    for module, service, fn in items:
        register_read_target(module, service, fn)


def _resolve(module: str, service: str, fn: str) -> Callable[..., Any]:
    key = (module, service, fn)
    if key in _HANDLER_CACHE:
        return _HANDLER_CACHE[key]
    if key not in _READ_ALLOWLIST:
        # Lazy bootstrap so workers/scripts/tests never hit an empty allowlist
        try:
            from app.modules.finance_os.bridges.erp_command_bridge.bootstrap import (
                bootstrap_wave1_boundaries,
                is_bootstrapped,
            )

            if not is_bootstrapped():
                bootstrap_wave1_boundaries()
            elif key not in _READ_ALLOWLIST:
                # Bootstrapped earlier without this target — register catalog reads once more
                from app.modules.finance_os.platform_ai_runtime.tools.catalog_read import READ_SPECS

                for spec in READ_SPECS:
                    if str(spec.module).startswith("app.modules.erp."):
                        register_read_target(spec.module, spec.service, spec.fn)
        except Exception:
            pass
    if key not in _READ_ALLOWLIST:
        raise PermissionError(f"erp_read_not_allowlisted:{module}.{service}.{fn}")
    mod = importlib.import_module(module)
    svc = getattr(mod, service)
    bound = getattr(svc, fn)
    if not callable(bound):
        raise ValueError(f"not_callable:{module}.{service}.{fn}")
    _HANDLER_CACHE[key] = bound
    return bound


def invoke_read(
    org_id: str,
    *,
    module: str,
    service: str,
    fn: str,
    kwargs: dict[str, Any] | None = None,
    org_style: str = "first",
) -> Any:
    """Invoke an allowlisted ERP read method. Finance OS must not import ERP repos/services."""
    kwargs = dict(kwargs or {})
    bound = _resolve(module, service, fn)
    try:
        sig = inspect.signature(bound)
        allowed = set(sig.parameters.keys())
        kwargs = {k: v for k, v in kwargs.items() if k in allowed}
    except Exception:
        pass
    if org_style == "kw":
        return bound(org_id=org_id, **kwargs)
    return bound(org_id, **kwargs)


class ErpQueryDispatch:
    """Facade singleton for ToolSpec target strings pointing at this service."""

    def call(
        self,
        org_id: str,
        *,
        target_module: str,
        target_service: str,
        target_fn: str,
        org_style: str = "first",
        **kwargs: Any,
    ) -> Any:
        return invoke_read(
            org_id,
            module=target_module,
            service=target_service,
            fn=target_fn,
            kwargs=kwargs,
            org_style=org_style,
        )


erp_query_dispatch = ErpQueryDispatch()


# --- Typed convenience facades (Finance OS production code should prefer these) ---


class APQueries:
    def find_vendor_by_gstin(self, org_id: str, *, gstin: str) -> dict | None:
        from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

        return vendor_repository.find_by_gstin(org_id, gstin=gstin)

    def list_invoices(self, org_id: str, **kwargs: Any) -> list[dict]:
        from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

        return invoice_repository.list(org_id, **kwargs)

    def list_outstanding_invoices(self, org_id: str) -> list[dict]:
        from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

        return invoice_repository.list_outstanding(org_id)

    def check_duplicate_invoice(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoice_number: str,
        total_amount: float,
        invoice_date: str,
    ) -> dict | None:
        from app.modules.erp.accounts_payable.services.duplicate_invoice_service import duplicate_invoice_service

        return duplicate_invoice_service.check_duplicate(
            org_id,
            vendor_id=vendor_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
        )


class ARQueries:
    def list_outstanding_invoices(self, org_id: str) -> list[dict]:
        from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

        return ar_invoice_repository.list_outstanding(org_id)

    def get_customer(self, org_id: str, *, customer_id: str) -> dict | None:
        from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository

        return customer_repository.get(org_id, customer_id=customer_id)


class TreasuryQueries:
    def compute_live_position(self, org_id: str) -> dict:
        from app.modules.erp.treasury.services.cash_position_service import cash_position_service

        return cash_position_service.compute_live_position(org_id)

    def list_cash_history(self, org_id: str, *, limit: int = 30) -> list[dict]:
        from app.modules.erp.treasury.repositories.cash_position_repository import cash_position_repository

        return cash_position_repository.list_history(org_id, limit=limit)

    def analyze_liquidity(self, org_id: str) -> dict:
        from app.modules.erp.treasury.services.liquidity_service import liquidity_service

        return liquidity_service.analyze(org_id)


class ReportingQueries:
    def schema_ready(self) -> bool:
        from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository

        return reporting_schema_repository.schema_ready()

    def get_ap_aging(self, org_id: str, **kwargs: Any) -> dict:
        from app.modules.erp.reporting.services.aging_report_service import aging_report_service

        return aging_report_service.get_ap(org_id, **kwargs)

    def get_ar_aging(self, org_id: str, **kwargs: Any) -> dict:
        from app.modules.erp.reporting.services.aging_report_service import aging_report_service

        return aging_report_service.get_ar(org_id, **kwargs)

    def get_pnl(self, org_id: str, **kwargs: Any) -> Any:
        from app.modules.erp.reporting.services.pnl_service import pnl_service

        return pnl_service.get(org_id, **kwargs)


class FiscalQueries:
    def get_period(self, org_id: str, *, period_id: str) -> dict | None:
        from app.modules.erp.fiscal.services.fiscal_period_service import fiscal_period_service

        return fiscal_period_service.get(org_id, period_id=period_id)

    def list_periods(self, org_id: str, **kwargs: Any) -> Any:
        from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository

        return fiscal_period_repository.list(org_id, **kwargs)

    def get_period_row(self, org_id: str, *, period_id: str) -> dict | None:
        from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository

        return fiscal_period_repository.get(org_id, period_id=period_id)


class InventoryQueries:
    def get_item_by_code(self, org_id: str, *, item_code: str) -> dict | None:
        from app.modules.erp.inventory.repositories.item_repository import item_repository

        return item_repository.get_by_code(org_id, item_code=item_code)

    def get_item(self, org_id: str, *, item_id: str) -> dict | None:
        from app.modules.erp.inventory.repositories.item_repository import item_repository

        return item_repository.get(org_id, item_id=item_id)


class ComplianceQueries:
    def list_obligations(self, org_id: str, **kwargs: Any) -> list[dict]:
        from app.modules.erp.compliance.repositories.compliance_repository import compliance_obligation_repository

        return compliance_obligation_repository.list(org_id, **kwargs)

    def dashboard(self, org_id: str, **kwargs: Any) -> Any:
        from app.modules.erp.compliance.services.compliance_dashboard_service import compliance_dashboard_service

        return compliance_dashboard_service.build(org_id, **kwargs)


class ReconciliationQueries:
    def run_scan(self, org_id: str, **kwargs: Any) -> Any:
        from app.modules.erp.reconciliation.jobs.reconciliation_scan_job import run_reconciliation_scan

        return run_reconciliation_scan(org_id, **kwargs)


ap_queries = APQueries()
ar_queries = ARQueries()
treasury_queries = TreasuryQueries()
reporting_queries = ReportingQueries()
fiscal_queries = FiscalQueries()
inventory_queries = InventoryQueries()
compliance_queries = ComplianceQueries()
reconciliation_queries = ReconciliationQueries()
