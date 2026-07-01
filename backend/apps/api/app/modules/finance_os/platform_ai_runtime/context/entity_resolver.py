from __future__ import annotations

import re

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import ConversationState, ResolvedEntity
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState

_PERIOD_PATTERNS = [
    (re.compile(r"\bq([1-4])\s*fy\s*(\d{4})\b", re.I), lambda m: f"Q{m.group(1)}-FY{m.group(2)}"),
    (re.compile(r"\blast quarter\b", re.I), lambda _: "last_quarter"),
    (re.compile(r"\bthis quarter\b", re.I), lambda _: "current_quarter"),
    (re.compile(r"\blast month\b", re.I), lambda _: "last_month"),
    (re.compile(r"\bthis month\b", re.I), lambda _: "current_month"),
]

_ENTITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "gst": ("gst", "cgst", "sgst", "igst", "tax return"),
    "vendor": ("vendor", "supplier"),
    "invoice": ("invoice", "bill"),
    "customer": ("customer", "client"),
    "po": ("purchase order", " po ", "po-"),
    "grn": ("grn", "goods receipt"),
    "bank": ("bank", "account balance"),
    "period": ("fiscal period", "financial year", "fy "),
    "asset": ("asset", "fixed asset"),
    "employee": ("employee", "staff", "payroll"),
}


class EntityResolver:
    def resolve(
        self,
        message: str,
        *,
        world_state: WorldState | None = None,
        working_memory: ConversationState | None = None,
    ) -> list[ResolvedEntity]:
        entities: list[ResolvedEntity] = []
        seen: set[str] = set()

        def add(entity_type: str, entity_id: str | None = None, *, label: str | None = None, source: str = "unknown", confidence: float = 0.5) -> None:
            key = f"{entity_type}:{entity_id or ''}"
            if key in seen:
                return
            seen.add(key)
            entities.append(
                ResolvedEntity(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    label=label,
                    source=source,
                    confidence=confidence,
                )
            )

        ws = world_state
        if ws and ws.screen:
            if ws.screen.entity_type:
                add(
                    ws.screen.entity_type,
                    ws.screen.entity_id,
                    source="screen",
                    confidence=0.95,
                )
        if ws and ws.selection:
            for key, val in ws.selection.items():
                if not val:
                    continue
                etype = key.replace("_id", "") if key.endswith("_id") else key
                add(etype, str(val), source="selection", confidence=0.9)

        wm = working_memory or ConversationState()
        if wm.current_entity:
            add(
                str(wm.current_entity.get("type") or "entity"),
                wm.current_entity.get("id"),
                source="working_memory",
                confidence=0.85,
            )
        if wm.current_vendor_id:
            add("vendor", wm.current_vendor_id, source="working_memory", confidence=0.85)
        if wm.current_period:
            add("period", wm.current_period, label=wm.current_period, source="working_memory", confidence=0.8)

        text = message.lower()
        for entity_type, keywords in _ENTITY_KEYWORDS.items():
            if any(k in text for k in keywords):
                add(entity_type, None, source="nlp_keyword", confidence=0.65)

        for pattern, fmt in _PERIOD_PATTERNS:
            m = pattern.search(message)
            if m:
                add("period", fmt(m), label=fmt(m), source="nlp_period", confidence=0.75)
                break

        id_match = re.search(r"\b([a-z]{2,5}[-_][\w-]+)\b", message, re.I)
        if id_match and not any(e.entity_id for e in entities if e.source == "screen"):
            add("entity", id_match.group(1), source="nlp_id", confidence=0.6)

        return entities


entity_resolver = EntityResolver()
