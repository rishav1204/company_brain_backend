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
}

_DEFAULT_SOURCES: list[tuple[str, str, str, dict]] = [
    ("memory", "memory", "search", {}),
    ("graph", "graph", "traverse", {}),
    ("bridge", "agent", "context", {}),
    ("documents", "documents", "search", {}),
]


def _entity_hint(entities: list[ResolvedEntity]) -> str | None:
    for e in entities:
        if e.entity_type in {"gst", "vendor", "invoice", "customer", "po", "grn", "bank", "period", "asset"}:
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
    if "analytics" in mod:
        return "analytics"
    if "procurement" in mod:
        return "procurement"
    return None


class ContextPlanner:
    def plan(
        self,
        *,
        intent: IntentResult,
        entities: list[ResolvedEntity],
        world_state: WorldState | None,
        message: str,
    ) -> RetrievalPlan:
        intent_key = intent.intent if intent.intent in {"read", "analysis"} else "read"
        hints: list[str] = list(intent.suggested_modules)
        entity_hint = _entity_hint(entities)
        if entity_hint:
            hints.insert(0, entity_hint)
        screen_mod = _screen_module(world_state)
        if screen_mod and screen_mod not in hints:
            hints.append(screen_mod)

        raw_sources: list[tuple[str, str, str, dict]] = []
        for hint in hints:
            key = (intent_key, hint)
            if key in _SOURCE_MAP:
                raw_sources.extend(_SOURCE_MAP[key])

        if world_state and world_state.screen and world_state.screen.entity_id:
            raw_sources.insert(0, ("bridge", "invoice", "context", {}))
            raw_sources.insert(1, ("graph", "graph", "traverse", {}))

        if not raw_sources:
            raw_sources = list(_DEFAULT_SOURCES)

        seen: set[str] = set()
        sources: list[RetrievalSource] = []
        for idx, (stype, tool, method, params) in enumerate(raw_sources):
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
                )
            )

        return RetrievalPlan(sources=sources, query=message, module_hints=hints)


context_planner = ContextPlanner()
