"""Allowlisted ERP mutation dispatch — the only place Finance OS may force-load ERP write services."""

from __future__ import annotations

import importlib
from typing import Any, Callable

from app.modules.finance_os.bridges.erp_command_bridge.exceptions import CommandTargetNotAllowlisted

_MUTATION_ALLOWLIST: set[tuple[str, str, str]] = set()
_CACHE: dict[tuple[str, str, str], Callable[..., Any]] = {}


def register_mutation_target(module: str, service: str, fn: str) -> None:
    if not module.startswith("app.modules.erp."):
        raise ValueError(f"mutation target must be ERP: {module}")
    if ".repositories." in module:
        raise ValueError(f"mutations must not target repositories: {module}")
    _MUTATION_ALLOWLIST.add((module, service, fn))


def register_mutation_targets(items: list[tuple[str, str, str]]) -> None:
    for m, s, f in items:
        register_mutation_target(m, s, f)


def is_allowlisted(module: str, service: str, fn: str) -> bool:
    return (module, service, fn) in _MUTATION_ALLOWLIST


def dispatch_erp_call(
    org_id: str,
    *,
    module: str,
    service: str,
    fn: str,
    kwargs: dict[str, Any],
    org_style: str = "first",
) -> Any:
    key = (module, service, fn)
    if key not in _MUTATION_ALLOWLIST:
        raise CommandTargetNotAllowlisted(f"erp_mutation_not_allowlisted:{module}.{service}.{fn}")
    if key not in _CACHE:
        mod = importlib.import_module(module)
        svc = getattr(mod, service)
        bound = getattr(svc, fn)
        if not callable(bound):
            raise ValueError(f"not_callable:{module}.{service}.{fn}")
        _CACHE[key] = bound
    bound = _CACHE[key]
    if org_style == "kw":
        return bound(org_id=org_id, **kwargs)
    return bound(org_id, **kwargs)
