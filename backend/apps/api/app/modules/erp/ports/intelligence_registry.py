"""ERP owns intelligence ports — Finance OS registers implementations at bootstrap."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class InvoiceIntelligencePort(Protocol):
    def run_pipeline(self, org_id: str, *, document_id: str, invoice_type: str = "purchase") -> dict: ...

    def get_extraction(self, org_id: str, extraction_id: str) -> dict | None: ...

    def latest_duplicate(self, org_id: str, extraction_id: str) -> dict | None: ...

    def list_anomalies(self, org_id: str, extraction_id: str) -> list[dict]: ...

    def list_suggestions(self, org_id: str, *, extraction_id: str) -> list[dict]: ...

    def list_predictions_for_extraction(self, org_id: str, extraction_id: str) -> list[dict]: ...

    def evaluate_confidence(
        self,
        *,
        extraction: dict,
        predictions: list[dict],
        duplicate_status: str,
        anomaly_count: int,
    ) -> dict: ...

    def link_prediction(self, org_id: str, prediction_id: str, *, ap_invoice_id: str) -> Any: ...


@runtime_checkable
class ForecastIntelligencePort(Protocol):
    def get_series(
        self,
        org_id: str,
        *,
        forecast_type: str = "cash",
        horizon_days: int = 30,
        as_of_date: str | None = None,
    ) -> dict: ...

    def actual_proxy(self, org_id: str, *, forecast_type: str, forecast_val: float) -> float: ...


@runtime_checkable
class ApRiskIntelligencePort(Protocol):
    """AP-04, AP-05, AP-06, AP-07, AP-08, AP-09."""

    def classify_vendor_from_extraction(self, extracted_data: dict) -> dict: ...

    def review_invoice_extraction(self, extracted_data: dict, *, vendor_gstin: str | None = None) -> dict: ...

    def duplicate_signals(self, dup_check: dict) -> dict: ...

    def suggest_ledger_accounts(self, extracted_data: dict, *, org_id: str | None = None) -> list[dict]: ...

    def assess_vendor_risk(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoices: list[dict],
        payments: list[dict],
    ) -> dict: ...

    def rank_invoices_for_payment(self, invoices: list[dict], *, as_of: str | None = None) -> list[dict]: ...

    def priority_score(self, invoice: dict, *, as_of: str | None = None) -> float: ...

    def forecast_cash_requirement(self, outstanding_invoices: list[dict], *, horizon_days: int = 30) -> dict: ...


@runtime_checkable
class JournalIntelligencePort(Protocol):
    """JR-02, JR-03, JR-04, JR-05."""

    def build_draft_lines_from_extraction(self, org_id: str, extracted_data: dict) -> tuple[list[dict], dict]: ...

    def score_journal_confidence(
        self,
        *,
        ledger_confidence: float,
        gst_confidence: float,
        vendor_confidence: float,
    ) -> dict: ...

    def requires_finance_review(self, ai_confidence: dict | None) -> bool: ...

    def detect_journal_anomalies(self, lines: list[dict], *, historical_avg: float | None = None) -> list[dict]: ...

    def suggest_accounts_for_journal(self, extracted_data: dict) -> list[dict]: ...


@runtime_checkable
class ExpenseIntelligencePort(Protocol):
    """EX-02, EX-03, EX-04, EX-05, EX-06."""

    def classify_expense(self, extracted_data: dict) -> str: ...

    def fraud_score(self, extracted_data: dict, *, amount: float) -> float: ...

    def detect_fraud(self, extracted_data: dict, *, amount: float) -> dict: ...

    def classify_duplicate(self, extracted_data: dict) -> dict: ...

    def analyze_spend(self, org_id: str, *, employee_id: str | None = None) -> dict: ...


@runtime_checkable
class ArCollectionsIntelligencePort(Protocol):
    """AR-02, AR-03, AR-04, AR-05."""

    def forecast_collections(self, invoices: list[dict], *, horizons: tuple[int, ...] = (7, 30, 60)) -> dict: ...

    def recommend_collections(self, invoices: list[dict], *, limit: int = 10) -> dict: ...

    def assess_payment_delay_risk(self, invoice: dict, *, customer_risk_score: float = 0.5) -> dict: ...

    def score_customer(self, *, invoices: list[dict], receipts: list[dict]) -> dict: ...


@runtime_checkable
class ReconciliationIntelligencePort(Protocol):
    """RC-01..RC-06 (ERP matching_engine stays ERP; FOS ranks, explains, answers)."""

    def suggest_matches(
        self,
        bank_tx: dict,
        ledger_entries: list[dict],
        *,
        subledger_candidates: list[dict] | None = None,
        rules: list[dict] | None = None,
        limit: int = 5,
    ) -> list[dict]: ...

    def score_breakdown(self, match_result: dict) -> dict: ...

    def classify_narration(self, narration: str) -> str: ...

    def detect_anomalies(
        self,
        *,
        bank_tx: dict,
        candidates: list[dict] | None = None,
        history_amounts: list[float] | None = None,
    ) -> list[dict]: ...

    def answer_question(self, **kwargs: Any) -> dict: ...


@runtime_checkable
class BankingIntelligencePort(Protocol):
    """BK-01..BK-05."""

    def detect_payment_anomalies(self, **kwargs: Any) -> dict: ...

    def classify_transaction(self, narration: str) -> str: ...

    def detect_transaction_anomalies(self, *, transactions: list[dict]) -> list[dict]: ...

    def answer_banking_question(self, **kwargs: Any) -> dict: ...

    def classify_narration(self, narration: str) -> dict: ...


@runtime_checkable
class TreasuryIntelligencePort(Protocol):
    """TR-01..TR-07."""

    def forecast_cashflow(self, *, inflows: list[dict], outflows: list[dict], horizon_days: int = 30) -> dict: ...

    def forecast_liquidity(self, *, inflows: list[dict], outflows: list[dict]) -> dict: ...

    def detect_cash_risks(self, **kwargs: Any) -> list[dict]: ...

    def detect_surplus_cash(self, *, accounts: list[dict], avg_daily_outflow: float) -> list[dict]: ...

    def advise_treasury(self, *, liquidity: dict, position: dict) -> list[dict]: ...

    def answer_treasury_question(self, *, question: str, position: dict, liquidity: dict) -> dict: ...

    def detect_payment_anomalies(self, **kwargs: Any) -> dict: ...


@runtime_checkable
class TaxIntelligencePort(Protocol):
    """TX-01..TX-10."""

    def recommend_section(self, **kwargs: Any) -> dict: ...

    def detect_tds_errors(self, **kwargs: Any) -> dict: ...

    def review_vendor_quarter(self, **kwargs: Any) -> dict: ...

    def review_return_payload(self, *, payload: dict, form_type: str) -> dict: ...

    def answer_tds_question(self, **kwargs: Any) -> dict: ...

    def detect_mismatches(self, our_tx: dict, gstr2b_row: dict) -> dict: ...

    def answer_gst_question(self, **kwargs: Any) -> dict: ...

    def assess_tax_risks(self, **kwargs: Any) -> dict: ...

    def vendor_mismatch_report(self, reconciliations: list[dict]) -> dict: ...

    def answer_compliance_question(self, **kwargs: Any) -> dict: ...

    def analyze_notice(self, *, notice_type: str, metadata: dict) -> dict: ...


@runtime_checkable
class ComplianceIntelligencePort(Protocol):
    """CM-01..CM-04."""

    def compute_risk_score(self, *, overdue: list[dict], escalations: list[dict], exposure: float) -> int: ...

    def detect_risks(self, *, obligations: list[dict], escalations: list[dict], exposure: float) -> dict: ...

    def predict_notice_risk(self, *, risk_flags: list[dict]) -> dict: ...

    def filing_readiness_score(self, **kwargs: Any) -> dict: ...

    def answer_compliance_question(self, **kwargs: Any) -> dict: ...


@runtime_checkable
class ProcurementIntelligencePort(Protocol):
    """PR-01..PR-04."""

    def analyze_spend(self, org_id: str) -> dict: ...

    def detect_anomalies(self, org_id: str) -> list[dict]: ...

    def recommend_vendors(self, org_id: str, *, item_hint: str = "", limit: int = 5) -> list[dict]: ...

    def answer_query(self, org_id: str, *, query: str) -> dict: ...


@runtime_checkable
class InventoryIntelligencePort(Protocol):
    """IN-01..IN-04."""

    def predict_demand(self, org_id: str, *, item_id: str, horizon_days: int = 30) -> dict: ...

    def classify_velocity(self, *, issue_count_30d: int, issue_count_90d: int) -> str: ...

    def detect_stock_risk(self, balances: list[dict], *, reorder_days: int = 14) -> list[dict]: ...

    def detect_dead_stock(self, movements: list[dict], *, as_of: str | None = None, days: int = 90) -> list[dict]: ...

    def analyze(self, org_id: str, *, query: str) -> dict: ...


@runtime_checkable
class AssetIntelligencePort(Protocol):
    """AS-01..AS-04."""

    def classify_asset(self, description: str) -> dict: ...

    def recommend_useful_life(self, hints: dict | None) -> int: ...

    def suggest(self, description: str, amount: float) -> dict: ...

    def detect_anomalies(self, assets: list[dict]) -> list[dict]: ...


class PortNotRegisteredError(RuntimeError):
    pass


class PortTimeoutError(TimeoutError):
    pass


@dataclass
class PortBinding:
    implementation: Any
    version: str = "v1"
    timeout_seconds: float | None = None
    fallback: Callable[..., Any] | None = None


#: Canonical port names. Finance OS registers one implementation per name.
PORT_NAMES: tuple[str, ...] = (
    "invoice",
    "forecast",
    "ap_risk",
    "journal",
    "expense",
    "ar_collections",
    "reconciliation",
    "banking",
    "treasury",
    "tax",
    "compliance",
    "procurement",
    "inventory",
    "asset",
)

_DEFAULT_TIMEOUTS: dict[str, float] = {
    "invoice": 120.0,
    "forecast": 60.0,
}


class IntelligenceRegistry:
    """
    Process-local registry.

    Spec: registration → discovery → invocation → optional timeout → optional fallback → versioning.
    Implementations are registered by Finance OS adapters; ERP modules never import finance_os.
    """

    def __init__(self) -> None:
        self._bindings: dict[str, PortBinding] = {}

    # --- registration -----------------------------------------------------

    def register(
        self,
        name: str,
        port: Any,
        *,
        version: str = "v1",
        timeout_seconds: float | None = None,
        fallback: Callable[..., Any] | None = None,
    ) -> None:
        if name not in PORT_NAMES:
            raise ValueError(f"unknown_intelligence_port:{name}")
        self._bindings[name] = PortBinding(
            port,
            version=version,
            timeout_seconds=_DEFAULT_TIMEOUTS.get(name, 30.0) if timeout_seconds is None else timeout_seconds,
            fallback=fallback,
        )

    def register_invoice(
        self,
        port: InvoiceIntelligencePort,
        *,
        version: str = "v1",
        timeout_seconds: float | None = 120.0,
        fallback: Callable[..., Any] | None = None,
    ) -> None:
        self.register("invoice", port, version=version, timeout_seconds=timeout_seconds, fallback=fallback)

    def register_forecast(
        self,
        port: ForecastIntelligencePort,
        *,
        version: str = "v1",
        timeout_seconds: float | None = 60.0,
        fallback: Callable[..., Any] | None = None,
    ) -> None:
        self.register("forecast", port, version=version, timeout_seconds=timeout_seconds, fallback=fallback)

    # --- discovery --------------------------------------------------------

    def _require(self, name: str) -> PortBinding:
        binding = self._bindings.get(name)
        if binding is None:
            raise PortNotRegisteredError(f"{name} intelligence port not registered (call finance_os bootstrap)")
        return binding

    def get(self, name: str) -> Any:
        return self._require(name).implementation

    def try_get(self, name: str) -> Any | None:
        binding = self._bindings.get(name)
        return binding.implementation if binding else None

    def version(self, name: str) -> str | None:
        binding = self._bindings.get(name)
        return binding.version if binding else None

    def is_registered(self, name: str) -> bool:
        return name in self._bindings

    # --- invocation -------------------------------------------------------

    def invoke(self, which: str, method: str, *args: Any, **kwargs: Any) -> Any:
        binding = self._require(which)
        fn = getattr(binding.implementation, method)
        try:
            if binding.timeout_seconds and binding.timeout_seconds > 0:
                started = time.monotonic()
                result = fn(*args, **kwargs)
                if time.monotonic() - started > binding.timeout_seconds:
                    if binding.fallback is not None:
                        return binding.fallback(*args, **kwargs)
                    raise PortTimeoutError(f"port_timeout:{which}.{method}")
                return result
            return fn(*args, **kwargs)
        except Exception:
            if binding.fallback is not None:
                return binding.fallback(*args, **kwargs)
            raise

    # --- typed accessors --------------------------------------------------

    def invoice(self) -> InvoiceIntelligencePort:
        return self.get("invoice")

    def forecast(self) -> ForecastIntelligencePort:
        return self.get("forecast")

    def ap_risk(self) -> ApRiskIntelligencePort:
        return self.get("ap_risk")

    def journal(self) -> JournalIntelligencePort:
        return self.get("journal")

    def expense(self) -> ExpenseIntelligencePort:
        return self.get("expense")

    def ar_collections(self) -> ArCollectionsIntelligencePort:
        return self.get("ar_collections")

    def reconciliation(self) -> ReconciliationIntelligencePort:
        return self.get("reconciliation")

    def banking(self) -> BankingIntelligencePort:
        return self.get("banking")

    def treasury(self) -> TreasuryIntelligencePort:
        return self.get("treasury")

    def tax(self) -> TaxIntelligencePort:
        return self.get("tax")

    def compliance(self) -> ComplianceIntelligencePort:
        return self.get("compliance")

    def procurement(self) -> ProcurementIntelligencePort:
        return self.get("procurement")

    def inventory(self) -> InventoryIntelligencePort:
        return self.get("inventory")

    def asset(self) -> AssetIntelligencePort:
        return self.get("asset")

    def try_invoice(self) -> InvoiceIntelligencePort | None:
        return self.try_get("invoice")

    def try_forecast(self) -> ForecastIntelligencePort | None:
        return self.try_get("forecast")

    def invoice_version(self) -> str | None:
        return self.version("invoice")

    def forecast_version(self) -> str | None:
        return self.version("forecast")

    def describe(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in PORT_NAMES:
            binding = self._bindings.get(name)
            out[name] = (
                {"registered": True, "version": binding.version, "timeout": binding.timeout_seconds}
                if binding
                else {"registered": False}
            )
        return out


intelligence_registry = IntelligenceRegistry()
