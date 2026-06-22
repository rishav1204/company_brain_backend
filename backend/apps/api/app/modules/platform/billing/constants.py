from __future__ import annotations

DEFAULT_PLAN_KEY = "finance_starter"

PLAN_KEYS = ("finance_starter", "finance_growth", "finance_os_pro", "enterprise")

FEATURE_CODES = (
    "coa", "gl", "journals", "vouchers", "ap", "ar", "gst", "tds", "compliance",
    "banking", "reporting", "procurement", "expense", "assets", "reconciliation",
    "treasury", "analytics", "audit_explorer", "invoice_ai", "workflow_intelligence",
    "memory", "graph_engine", "agents", "forecasting", "api_platform",
    "consolidation", "multi_entity",
)

LIMIT_CODES = (
    "max_users", "max_entities", "max_gstins", "invoices_monthly",
    "api_calls_monthly", "workflow_runs_monthly", "storage_gb",
)

METRIC_CODES = (
    "users", "entities", "gstins", "invoices", "api_calls", "workflow_runs",
)

# Customer-facing credit costs per AI operation
CREDIT_CATALOG: dict[str, float] = {
    "invoice_ocr": 1.0,
    "invoice_ai_review": 2.0,
    "invoice_extraction": 5.0,
    "invoice_classification": 2.0,
    "workflow_intelligence": 2.0,
    "workflow_suggestion": 3.0,
    "memory_write": 1.0,
    "memory_embedding": 1.0,
    "graph_ingest": 1.0,
    "graph_query": 2.0,
    "agent_execution": 10.0,
    "custom_workflow_agent": 15.0,
    "forecast_generation": 5.0,
    "forecast_run": 8.0,
    "reconciliation_analysis": 3.0,
    "audit_copilot": 5.0,
    "analytics_insight": 4.0,
    "generic_llm": 1.0,
}

# Fallback plan matrix when DB schema not ready (tests / dev)
PLAN_FEATURES: dict[str, frozenset[str]] = {
    "finance_starter": frozenset({
        "coa", "gl", "journals", "vouchers", "ap", "ar", "gst", "tds", "compliance",
        "banking", "reporting",
    }),
    "finance_growth": frozenset({
        "coa", "gl", "journals", "vouchers", "ap", "ar", "gst", "tds", "compliance",
        "banking", "reporting", "procurement", "expense", "assets", "reconciliation",
        "treasury", "analytics", "audit_explorer",
    }),
    "finance_os_pro": frozenset({
        "coa", "gl", "journals", "vouchers", "ap", "ar", "gst", "tds", "compliance",
        "banking", "reporting", "procurement", "expense", "assets", "reconciliation",
        "treasury", "analytics", "audit_explorer", "invoice_ai", "workflow_intelligence",
        "memory", "graph_engine", "agents", "forecasting", "api_platform",
    }),
    "enterprise": frozenset({
        "coa", "gl", "journals", "vouchers", "ap", "ar", "gst", "tds", "compliance",
        "banking", "reporting", "procurement", "expense", "assets", "reconciliation",
        "treasury", "analytics", "audit_explorer", "invoice_ai", "workflow_intelligence",
        "memory", "graph_engine", "agents", "forecasting", "api_platform",
        "consolidation", "multi_entity",
    }),
}

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "finance_starter": {"max_users": 5, "max_entities": 1, "max_gstins": 1, "api_calls_monthly": 10000},
    "finance_growth": {"max_users": 25, "max_entities": 3, "max_gstins": 3, "api_calls_monthly": 50000},
    "finance_os_pro": {"max_users": 100, "max_entities": 10, "max_gstins": 10, "api_calls_monthly": 200000},
    "enterprise": {},
}

PLAN_INCLUDED_CREDITS: dict[str, float] = {
    "finance_starter": 0,
    "finance_growth": 500,
    "finance_os_pro": 2000,
    "enterprise": 0,
}
