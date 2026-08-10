"""Wave 2 financial event governance — contracts, criticality, ownership rules."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from app.modules.platform.events.bus.event_registry import ALL_EVENTS, EventDefinition, get_event_definition


# Explicit financial / ledger-critical event families (authoritative for same-TX + strict registry).
_FINANCIAL_PREFIXES = (
    "journal.",
    "erp.journal.",
    "erp.ledger.",
    "erp.invoice.",
    "erp.payment.",
    "payment.",
    "invoice.",
    "sales.invoice.",
    "ledger.",
    "gst.",
    "tds.",
    "erp.period.",
    "erp.fiscal",
    "erp.year_end.",
    "pr.",
    "po.",
    "grn.",
    "expense.",
    "asset.",
    "inventory.",
    "bank.",
    "customer.payment.",
    "erp.command.",
)


def is_financial_event_type(event_type: str) -> bool:
    et = str(event_type or "")
    definition = get_event_definition(et)
    if definition is not None and getattr(definition, "financial", False):
        return True
    return any(et.startswith(p) for p in _FINANCIAL_PREFIXES)


@dataclass(frozen=True)
class EventContract:
    """Enterprise event contract surface (registry + governance metadata)."""

    event_type: str
    version: str
    owner: str
    category: str
    financial: bool
    criticality: str  # low|normal|high|critical
    replayable: bool
    ordering: str  # none|entity|partition
    pii: bool
    deprecated: bool
    description: str = ""
    producers: tuple[str, ...] = ()
    consumers: tuple[str, ...] = ()
    schema_ref: str = "canonical.v1"
    retention_days: int = 90
    backward_compatible: bool = True

    @classmethod
    def from_definition(cls, definition: EventDefinition) -> "EventContract":
        financial = bool(getattr(definition, "financial", False)) or is_financial_event_type(definition.event_type)
        criticality = "critical" if financial else "normal"
        ordering = "entity" if financial else "none"
        return cls(
            event_type=definition.event_type,
            version=definition.version or "v1",
            owner=definition.owner,
            category=definition.category,
            financial=financial,
            criticality=criticality,
            replayable=True,
            ordering=ordering,
            pii=False,
            deprecated=bool(getattr(definition, "deprecated", False)),
            description=getattr(definition, "description", "") or "",
            producers=(definition.owner,),
            consumers=(),
            schema_ref=f"canonical.{definition.version or 'v1'}",
            retention_days=365 if financial else 90,
            backward_compatible=True,
        )

    def qualified_name(self) -> str:
        """journal.created.v1 style — version is suffix not renaming."""
        base = self.event_type
        if base.endswith(f".{self.version}"):
            return base
        return f"{base}.{self.version}"


def list_contracts() -> list[EventContract]:
    return [EventContract.from_definition(d) for d in ALL_EVENTS.values()]


def get_contract(event_type: str) -> EventContract | None:
    d = get_event_definition(event_type)
    if not d:
        # still classify unregistered financial by prefix
        if is_financial_event_type(event_type):
            return EventContract(
                event_type=event_type,
                version="v1",
                owner="unknown",
                category="domain",
                financial=True,
                criticality="critical",
                replayable=True,
                ordering="entity",
                pii=False,
                deprecated=False,
                description="Unregistered financial event — must be registered",
            )
        return None
    return EventContract.from_definition(d)


def require_financial_registered(event_type: str) -> None:
    from app.core.config import settings

    if not settings.event_require_registered_financial:
        return
    if not is_financial_event_type(event_type):
        return
    if get_event_definition(event_type) is None:
        raise ValueError(f"financial_event_not_registered:{event_type}")


def duplicate_event_types(definitions: Iterable[EventDefinition] | None = None) -> list[str]:
    """Detect accidental duplicate keys if registry built from list with collisions."""
    seen: set[str] = set()
    dups: list[str] = []
    # ALL_EVENTS is already a dict — duplicates folded; scan raw tuples if provided
    if definitions is None:
        return []
    for d in definitions:
        if d.event_type in seen:
            dups.append(d.event_type)
        seen.add(d.event_type)
    return dups


def version_compat(old_version: str, new_version: str) -> bool:
    """vN -> vN+1 is considered compatible major bump documentation-wise."""
    def _n(v: str) -> int:
        s = str(v or "v1").lower().lstrip("v")
        try:
            return int(s.split(".")[0])
        except ValueError:
            return 1

    return _n(new_version) >= _n(old_version)


# Ordering key helper for financial envelopes
def ordering_key(*, entity_type: str | None, entity_id: str | None, event_type: str) -> str | None:
    if entity_type and entity_id:
        return f"{entity_type}:{entity_id}"
    if entity_id:
        return str(entity_id)
    if is_financial_event_type(event_type):
        return event_type
    return None


def partition_key(*, org_id: str, entity_id: str | None = None) -> str:
    if entity_id:
        return f"{org_id}:{entity_id}"
    return org_id
