"""Query registry — named ERP reads for Finance OS (no ad-hoc repo sprawl)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class QueryNotRegisteredError(KeyError):
    pass


Handler = Callable[..., Any]


@dataclass(frozen=True)
class QueryRegistration:
    name: str  # e.g. GetVendorByGstin, GetInvoice, GetCashPosition
    description: str = ""
    # Either a callable factory bound at register time, or module triple for invoke_read
    erp_module: str | None = None
    erp_service: str | None = None
    erp_fn: str | None = None
    org_style: str = "first"
    handler: Handler | None = None
    tags: tuple[str, ...] = ()


class QueryRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, QueryRegistration] = {}

    def register(self, reg: QueryRegistration) -> None:
        if reg.handler is None and not (reg.erp_module and reg.erp_service and reg.erp_fn):
            raise ValueError(f"query {reg.name} needs handler or erp target")
        self._by_name[reg.name] = reg
        self._by_name[reg.name.lower()] = reg
        if reg.erp_module and reg.erp_service and reg.erp_fn:
            from app.modules.erp.query_services.dispatch import register_read_target

            register_read_target(reg.erp_module, reg.erp_service, reg.erp_fn)

    def get(self, name: str) -> QueryRegistration:
        reg = self._by_name.get(name) or self._by_name.get(name.lower())
        if not reg:
            raise QueryNotRegisteredError(f"query_not_registered:{name}")
        return reg

    def execute(self, name: str, org_id: str, **kwargs: Any) -> Any:
        reg = self.get(name)
        if reg.handler is not None:
            return reg.handler(org_id, **kwargs)
        from app.modules.erp.query_services.dispatch import invoke_read

        return invoke_read(
            org_id,
            module=str(reg.erp_module),
            service=str(reg.erp_service),
            fn=str(reg.erp_fn),
            kwargs=kwargs,
            org_style=reg.org_style,
        )

    def list_queries(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for reg in self._by_name.values():
            if reg.name in seen:
                continue
            seen.add(reg.name)
            out.append(
                {
                    "name": reg.name,
                    "description": reg.description,
                    "erp_module": reg.erp_module,
                    "erp_service": reg.erp_service,
                    "erp_fn": reg.erp_fn,
                    "has_handler": reg.handler is not None,
                    "tags": list(reg.tags),
                }
            )
        return sorted(out, key=lambda x: x["name"])


query_registry = QueryRegistry()
