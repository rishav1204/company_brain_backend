from __future__ import annotations

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
        ("erp", "forecasting", "latest", {}),
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
}

# Cross-module expands when user is on a primary entity (invoice-centric chain)
_CROSS_MODULE: dict[str, list[tuple[str, str, str, dict]]] = {
    "invoice": [
        ("erp", "ap", "get_vendor", {}),
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
        }:
            return e.entity_type
    return None


def _screen_module(world_state: WorldState | None) -> str | None:
    if not world_state or not world_state.screen or not world_state.screen.module:
        return None
    mod = world_state.screen.module.lower()
    if "ap" in mod or "payable" in mod:
        return "ap"
    if "ar" in mod or "receivable" in mod:
        return "ar"
    if "gst" in mod or "tax" in mod:
        return "gst"
    if "treasury" in mod or "cash" in mod:
        return "treasury"
    if "inventory" in mod:
        return "inventory"
    if "analytics" in mod or "dashboard" in mod:
        return "analytics"
    if "procurement" in mod or "purchase" in mod:
        return "procurement"
    if "journal" in mod or "gl" in mod:
        return "journal"
    if "workflow" in mod:
        return "workflow"
    if "approval" in mod:
        return "approval"
    return None


def _message_hints(message: str) -> list[str]:
    text = (message or "").lower()
    hints: list[str] = []
    mapping = (
        ("invoice", "invoice"),
        ("vendor", "vendor"),
        ("supplier", "vendor"),
        ("customer", "customer"),
        ("overdue", "ar"),
        ("gst", "gst"),
        ("cash", "treasury"),
        ("treasury", "treasury"),
        ("purchase order", "po"),
        (" po ", "po"),
        ("journal", "journal"),
        ("approval", "approval"),
        ("workflow", "workflow"),
        ("blocked", "approval"),
        ("dashboard", "analytics"),
    )
    for needle, hint in mapping:
        if needle in text and hint not in hints:
            hints.append(hint)
    return hints


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
        for idx, (stype, tool, method, params, cross) in enumerate(raw_sources):
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
