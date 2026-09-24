from __future__ import annotations

import re

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    IntentResult,
    ResolvedEntity,
    RetrievalPlan,
    RetrievalSource,
)
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState

# Declarative map: (intent, module_hint|entity_type) -> retrieval sources
_SOURCE_MAP: dict[tuple[str, str], list[tuple[str, str, str, dict]]] = {
    ("read", "gst"): [
        ("erp", "tax_gst", "list_returns", {}),
        ("bridge", "gst", "compliance", {}),
        ("memory", "memory", "search", {"memory_type": "compliance"}),
    ],
    ("analysis", "gst"): [
        ("erp", "tax_gst", "list_returns", {}),
        ("erp", "gl", "trial_balance", {}),
        ("bridge", "gst", "compliance", {}),
        ("memory", "memory", "search", {}),
        ("graph", "graph", "traverse", {}),
    ],
    ("read", "ap"): [
        ("erp", "ap", "list_outstanding", {}),
        ("erp", "ap", "list_invoices", {}),
        ("bridge", "invoice", "context", {}),
        ("memory", "memory", "search", {}),
        ("graph", "graph", "traverse", {}),
    ],
    ("analysis", "ap"): [
        ("erp", "ap", "list_outstanding", {}),
        ("erp", "ap", "list_invoices", {}),
        ("bridge", "invoice", "context", {}),
        ("memory", "memory", "search", {}),
        ("graph", "graph", "traverse", {}),
        ("documents", "documents", "search", {}),
    ],
    ("read", "invoice"): [
        ("bridge", "invoice", "context", {}),
        ("erp", "ap", "get_invoice", {}),
        ("graph", "graph", "traverse", {}),
        ("memory", "memory", "search", {}),
        ("platform", "approval_queue", "list", {}),
    ],
    ("read", "vendor"): [
        ("erp", "ap", "get_vendor", {}),
        ("erp", "ap", "list_invoices", {}),
        ("graph", "graph", "traverse", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "ar"): [
        ("erp", "ar", "list_outstanding", {}),
        ("erp", "ar", "list_overdue", {}),
        ("memory", "memory", "search", {}),
    ],
    ("analysis", "treasury"): [
        ("erp", "treasury", "get_cash_position", {}),
        ("erp", "ar", "list_outstanding", {}),
        ("erp", "ap", "list_outstanding", {}),
        ("erp", "forecasting", "list_forecasts", {}),
        ("memory", "memory", "search", {}),
        ("graph", "graph", "traverse", {}),
    ],
    ("read", "treasury"): [
        ("erp", "treasury", "get_cash_position", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "inventory"): [
        ("erp", "inventory", "list_balances", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "analytics"): [
        ("erp", "analytics", "executive_dashboard", {}),
        ("memory", "memory", "search", {}),
    ],
    ("analysis", "analytics"): [
        ("erp", "analytics", "executive_dashboard", {}),
        ("erp", "analytics", "list_insights", {}),
        ("memory", "memory", "search", {}),
        ("documents", "documents", "search", {}),
    ],
    ("read", "procurement"): [
        ("erp", "procurement", "list_pos", {}),
        ("memory", "memory", "search", {}),
        ("graph", "graph", "traverse", {}),
    ],
    ("read", "po"): [
        ("erp", "procurement", "get_po", {}),
        ("erp", "procurement", "list_grns", {}),
        ("graph", "graph", "traverse", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "journal"): [
        ("erp", "journals", "get", {}),
        ("erp", "journals", "list_approval_queue", {}),
        ("graph", "graph", "traverse", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "workflow"): [
        ("platform", "workflow_state", "active", {}),
        ("platform", "approval_queue", "list", {}),
        ("memory", "memory", "search", {}),
    ],
    ("workflow", "workflow"): [
        ("platform", "workflow_state", "active", {}),
        ("platform", "approval_queue", "list", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "approval"): [
        ("platform", "approval_queue", "list", {}),
        ("erp", "journals", "list_approval_queue", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "voucher"): [
        ("erp", "vouchers", "list", {}),
        ("erp", "vouchers", "get", {}),
        ("graph", "graph", "traverse", {}),
        ("memory", "memory", "search", {}),
        ("platform", "approval_queue", "list", {}),
    ],
    ("read", "vouchers"): [
        ("erp", "vouchers", "list", {}),
        ("memory", "memory", "search", {}),
        ("platform", "approval_queue", "list", {}),
    ],
    ("read", "banking"): [
        ("erp", "banking", "list_accounts", {}),
        ("erp", "banking", "list_transactions", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "bank"): [
        ("erp", "banking", "list_accounts", {}),
        ("erp", "banking", "get_account", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "assets"): [
        ("erp", "assets", "list", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "asset"): [
        ("erp", "assets", "get", {}),
        ("erp", "assets", "list", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "expenses"): [
        ("erp", "expenses", "list_claims", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "claim"): [
        ("erp", "expenses", "get_claim", {}),
        ("erp", "expenses", "list_claims", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "customer"): [
        ("erp", "ar", "get_customer", {}),
        ("erp", "ar", "list_outstanding", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "compliance"): [
        ("erp", "compliance", "dashboard", {}),
        ("erp", "compliance", "upcoming", {}),
        ("memory", "memory", "search", {}),
    ],
    ("read", "tax"): [
        ("erp", "tax_gst", "list_returns", {}),
        ("bridge", "gst", "compliance", {}),
        ("memory", "memory", "search", {}),
    ],
}

# Cross-module expands when user is on a primary entity (invoice-centric chain)
_CROSS_MODULE: dict[str, list[tuple[str, str, str, dict]]] = {
    "invoice": [
        ("graph", "graph", "traverse", {}),
        ("bridge", "gst", "compliance", {}),
        ("platform", "approval_queue", "list", {}),
    ],
    "vendor": [
        ("erp", "ap", "list_invoices", {}),
        ("erp", "ap", "list_outstanding", {}),
        ("graph", "graph", "traverse", {}),
    ],
    "po": [
        ("erp", "procurement", "list_grns", {}),
        ("erp", "ap", "list_invoices", {}),
        ("graph", "graph", "traverse", {}),
    ],
    "customer": [
        ("erp", "ar", "list_outstanding", {}),
        ("erp", "ar", "list_overdue", {}),
        ("graph", "graph", "traverse", {}),
    ],
    "voucher": [
        ("graph", "graph", "traverse", {}),
        ("platform", "approval_queue", "list", {}),
    ],
}

_DEFAULT_SOURCES: list[tuple[str, str, str, dict]] = [
    ("memory", "memory", "search", {}),
    ("graph", "graph", "traverse", {}),
    ("bridge", "agent", "context", {}),
    ("documents", "documents", "search", {}),
    ("platform", "ui_context", "current", {}),
]


def _entity_hint(entities: list[ResolvedEntity]) -> str | None:
    for e in entities:
        if e.entity_type in {
            "gst",
            "vendor",
            "invoice",
            "customer",
            "po",
            "grn",
            "bank",
            "period",
            "asset",
            "journal",
            "approval",
            "workflow",
            "voucher",
            "claim",
        }:
            return e.entity_type
    return None


def _screen_module(world_state: WorldState | None) -> str | None:
    if not world_state or not world_state.screen or not world_state.screen.module:
        return None
    mod = world_state.screen.module.lower().strip()
    # Use token / phrase checks — substring "ar" matches "dashboard" otherwise
    tokens = set(re.split(r"[^a-z0-9]+", mod))
    if tokens & {"ap", "payable", "payables"} or "accounts payable" in mod:
        return "ap"
    if tokens & {"ar", "receivable", "receivables"} or "accounts receivable" in mod:
        return "ar"
    if tokens & {"gst", "tax"} or "tax" in mod:
        return "gst"
    if tokens & {"treasury", "cash"} or "treasury" in mod or "cash" in mod:
        return "treasury"
    if "inventory" in tokens or "inventory" in mod:
        return "inventory"
    if tokens & {"voucher", "vouchers"} or "voucher" in mod:
        return "vouchers"
    if tokens & {"banking", "bank"} or "banking" in mod:
        return "banking"
    if tokens & {"asset", "assets"} or "asset" in mod:
        return "assets"
    if tokens & {"expense", "expenses", "claim"} or "expense" in mod:
        return "expenses"
    if tokens & {"compliance"} or "compliance" in mod:
        return "compliance"
    if tokens & {"analytics", "dashboard"} or "analytics" in mod or "dashboard" in mod:
        return "analytics"
    if tokens & {"procurement", "purchase"} or "procurement" in mod or "purchase" in mod:
        return "procurement"
    if tokens & {"journal", "journals", "gl"} or "journal" in mod:
        return "journal"
    if "workflow" in tokens or "workflow" in mod:
        return "workflow"
    if "approval" in tokens or "approval" in mod:
        return "approval"
    return None


def _message_hints(message: str) -> list[str]:
    text = (message or "").lower()
    hints: list[str] = []
    # Prefer AP/AR list intents over single-invoice detail when wording is list-like
    ap_list = any(
        w in text
        for w in (
            "unpaid",
            "outstanding",
            "accounts payable",
            " ap ",
            "ap invoice",
            "ap invoices",
            "payable",
        )
    ) or text.strip().startswith("ap ") or "show my unpaid" in text
    ar_list = any(w in text for w in ("accounts receivable", " ar ", "ar invoice", "customer invoice", "receivable"))
    # Vendor bill payment asks ("why hasn't INV-001 been paid?") → AP, not AR
    inv_code = bool(re.search(r"\binv[-_]?\d+\b", text))
    voucher_code = bool(re.search(r"\b(vch|jv|pv|rv)[-_]?\w*\d+\b", text))
    payment_ask = any(w in text for w in ("paid", "payment", "pay ", " unpaid"))
    if inv_code and payment_ask and not ar_list:
        ap_list = True
    if ap_list:
        hints.append("ap")
    if ar_list:
        hints.append("ar")
    # "overdue" alone is ambiguous — bias to AP if payable words present, else AR
    if "overdue" in text:
        if ap_list or "payable" in text or "ap" in text:
            if "ap" not in hints:
                hints.append("ap")
        elif "ar" not in hints:
            hints.append("ar")

    mapping = (
        ("voucher", "voucher"),
        ("journal voucher", "voucher"),
        ("gst", "gst"),
        ("vendor", "vendor"),
        ("supplier", "vendor"),
        ("customer", "customer"),
        ("cash", "treasury"),
        ("treasury", "treasury"),
        ("purchase order", "po"),
        (" po ", "po"),
        ("journal", "journal"),
        ("approval", "approval"),
        ("workflow", "workflow"),
        ("blocked", "approval"),
        ("bank account", "banking"),
        ("banking", "banking"),
        ("fixed asset", "asset"),
        ("asset register", "assets"),
        ("expense claim", "expenses"),
        ("expense", "expenses"),
        ("compliance", "compliance"),
        ("dashboard", "analytics"),
        ("kpi", "analytics"),
    )
    for needle, hint in mapping:
        if needle in text and hint not in hints:
            hints.append(hint)

    # Concrete document codes
    if inv_code or "this invoice" in text or "invoice detail" in text:
        if "invoice" not in hints:
            hints.append("invoice")
    elif voucher_code or "this voucher" in text:
        if "voucher" not in hints:
            hints.append("voucher")
    elif "invoice" in text and "ap" not in hints and "ar" not in hints and "voucher" not in hints:
        # Generic invoice list question → AP list map (most common ERP ask)
        hints.append("ap")
    return hints


_DETAIL_METHODS = {
    ("ap", "get_invoice"),
    ("ap", "get_vendor"),
    ("ar", "get_invoice"),
    ("ar", "get_customer"),
    ("journals", "get"),
    ("procurement", "get_po"),
    ("vouchers", "get"),
    ("coa", "get_account"),
    ("banking", "get_account"),
}


def _has_detail_id(world_state: WorldState | None, entities: list[ResolvedEntity], message: str) -> bool:
    if world_state and world_state.screen and world_state.screen.entity_id:
        return True
    if world_state and (world_state.current_invoice_id or world_state.current_vendor_id or world_state.current_customer_id):
        return True
    if any(e.entity_id for e in entities if e.entity_id and str(e.entity_id).lower() not in {"invoice", "voucher", "vendor"}):
        return True
    text = (message or "").lower()
    if re.search(r"\binv[-_]?\d+\b", text):
        return True
    if re.search(r"\b(vch|jv|pv|rv|po|grn)[-_]?\w*\d+\b", text):
        return True
    return False


class ContextPlanner:
    """Determines exactly which sources are required — never load everything (Wave 4)."""

    def plan(
        self,
        *,
        intent: IntentResult,
        entities: list[ResolvedEntity],
        world_state: WorldState | None,
        message: str,
        include_cross_module: bool = True,
    ) -> RetrievalPlan:
        intent_key = intent.intent if intent.intent in {"read", "analysis", "workflow"} else "read"
        hints: list[str] = list(intent.suggested_modules)
        entity_hint = _entity_hint(entities)
        if entity_hint:
            hints.insert(0, entity_hint)
        screen_mod = _screen_module(world_state)
        if screen_mod and screen_mod not in hints:
            hints.insert(0, screen_mod)
        if world_state and world_state.screen and world_state.screen.entity_type:
            et = world_state.screen.entity_type.lower()
            if et not in hints:
                hints.insert(0, et)
        for h in _message_hints(message):
            if h not in hints:
                hints.append(h)

        raw_sources: list[tuple[str, str, str, dict, bool]] = []
        reasons: list[str] = []

        for hint in hints:
            key = (intent_key, hint)
            if key in _SOURCE_MAP:
                for stype, tool, method, params in _SOURCE_MAP[key]:
                    raw_sources.append((stype, tool, method, params, False))
                reasons.append(f"map:{intent_key}+{hint}")
            # fallback: try read map if analysis missing
            elif intent_key != "read" and ("read", hint) in _SOURCE_MAP:
                for stype, tool, method, params in _SOURCE_MAP[("read", hint)]:
                    raw_sources.append((stype, tool, method, params, False))
                reasons.append(f"map:read+{hint}")

        # Current screen entity — always boost object + graph + UI snapshot
        if world_state and world_state.screen and world_state.screen.entity_id:
            raw_sources.insert(0, ("platform", "ui_context", "current", {}, False))
            raw_sources.insert(1, ("bridge", "invoice", "context", {}, False))
            raw_sources.insert(2, ("graph", "graph", "traverse", {}, False))
            reasons.append("screen_entity")

        # Active workflows / approvals when present on world state
        if world_state and (world_state.active_workflows or world_state.pending_approvals):
            raw_sources.append(("platform", "workflow_state", "active", {}, False))
            raw_sources.append(("platform", "approval_queue", "list", {}, False))
            reasons.append("active_workflow_or_approval")

        # Cross-module relationship expand for primary object
        if include_cross_module:
            primary = entity_hint or (
                world_state.screen.entity_type.lower()
                if world_state and world_state.screen and world_state.screen.entity_type
                else None
            )
            if primary and primary in _CROSS_MODULE:
                for stype, tool, method, params in _CROSS_MODULE[primary]:
                    raw_sources.append((stype, tool, method, params, True))
                reasons.append(f"cross_module:{primary}")

        if not raw_sources:
            for stype, tool, method, params in _DEFAULT_SOURCES:
                raw_sources.append((stype, tool, method, params, False))
            reasons.append("default")

        seen: set[str] = set()
        sources: list[RetrievalSource] = []
        allow_detail = _has_detail_id(world_state, entities, message)
        for idx, (stype, tool, method, params, cross) in enumerate(raw_sources):
            # Skip single-object getters when no entity id is in context (avoids noisy Missing required params)
            if (tool, method) in _DETAIL_METHODS and not allow_detail:
                continue
            # AP unpaid/list / INV payment questions should not also pull unrelated AR tools
            text_l = (message or "").lower()
            if (
                "ap" in hints
                and "ar" not in hints
                and tool == "ar"
                and any(
                    w in text_l
                    for w in (
                        "unpaid",
                        "payable",
                        "ap invoice",
                        "accounts payable",
                        "paid",
                        "payment",
                    )
                )
            ):
                continue
            # Invoice document codes → prefer AP get over AR get unless AR was hinted
            if (
                re.search(r"\binv[-_]?\d+\b", text_l)
                and "ar" not in hints
                and tool == "ar"
                and method in {"get_invoice", "list_outstanding", "list_overdue"}
            ):
                continue
            # Specific domain asks from Dashboard should not dump KPI analytics
            domain_focus = any(
                h in hints
                for h in (
                    "voucher",
                    "vouchers",
                    "banking",
                    "bank",
                    "assets",
                    "asset",
                    "expenses",
                    "claim",
                    "journal",
                    "procurement",
                    "po",
                    "compliance",
                    "tax",
                    "gst",
                )
            )
            if tool == "analytics" and domain_focus:
                continue
            # Specific invoice asks should not dump the executive KPI dashboard
            if re.search(r"\binv[-_]?\d+\b", text_l) and tool == "analytics":
                continue
            # AP unpaid/list asks from Dashboard should use AP tools, not KPI dump
            if (
                tool == "analytics"
                and "ap" in hints
                and any(w in text_l for w in ("unpaid", "outstanding", "payable", "ap invoice", "accounts payable"))
            ):
                continue
            sig = f"{stype}:{tool}.{method}"
            if sig in seen:
                continue
            seen.add(sig)
            sources.append(
                RetrievalSource(
                    source_type=stype,
                    tool=tool,
                    method=method,
                    params=dict(params),
                    priority=idx + 1,
                    cross_module=cross,
                )
            )

        return RetrievalPlan(
            sources=sources,
            query=message,
            module_hints=hints,
            plan_reason=";".join(reasons[:8]),
            required_modules=hints[:6],
        )


context_planner = ContextPlanner()
