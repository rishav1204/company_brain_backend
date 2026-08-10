"""Command registry — primary extensibility surface for ERP mutations from Finance OS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.modules.finance_os.bridges.erp_command_bridge.exceptions import CommandNotRegisteredError

HandlerFn = Callable[..., Any]


@dataclass(frozen=True)
class CommandRegistration:
    """Declarative command metadata. Adding a command = register one of these."""

    name: str  # e.g. CreateVoucherFromExtraction, ap.create_invoice
    erp_module: str
    erp_service: str
    erp_fn: str
    policy_action: str | None = None
    requires_approval: bool = False
    allowed_roles: tuple[str, ...] = ()
    org_style: str = "first"
    max_attempts: int = 1
    idempotent: bool = True
    description: str = ""
    # Optional custom validator: (ErpCommand) -> None
    validator: Callable[[Any], None] | None = None
    # Optional payload key mapping defaults
    required_payload_keys: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def erp_target(self) -> tuple[str, str, str]:
        return (self.erp_module, self.erp_service, self.erp_fn)


class CommandRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, CommandRegistration] = {}
        self._by_tool: dict[tuple[str, str], str] = {}

    def register(self, reg: CommandRegistration, *, tool: str | None = None, method: str | None = None) -> None:
        if not reg.erp_module.startswith("app.modules.erp."):
            raise ValueError(f"command {reg.name} must target ERP services module")
        if ".repositories." in reg.erp_module:
            raise ValueError(f"command {reg.name} must not target repositories")
        key = reg.name.strip()
        self._by_name[key] = reg
        self._by_name[key.lower()] = reg
        if tool and method:
            self._by_tool[(tool.lower(), method.lower())] = key
        # also sync mutation allowlist
        from app.modules.finance_os.bridges.erp_command_bridge.handlers.erp_dispatch import register_mutation_target

        register_mutation_target(reg.erp_module, reg.erp_service, reg.erp_fn)

    def get(self, name: str) -> CommandRegistration:
        reg = self._by_name.get(name) or self._by_name.get(name.lower())
        if not reg:
            raise CommandNotRegisteredError(f"command_not_registered:{name}")
        return reg

    def get_optional(self, name: str) -> CommandRegistration | None:
        return self._by_name.get(name) or self._by_name.get(name.lower())

    def get_by_tool(self, tool: str, method: str) -> CommandRegistration | None:
        name = self._by_tool.get((tool.lower(), method.lower()))
        return self.get_optional(name) if name else None

    def list_commands(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for name, reg in self._by_name.items():
            if reg.name in seen:
                continue
            seen.add(reg.name)
            out.append(
                {
                    "name": reg.name,
                    "erp_module": reg.erp_module,
                    "erp_service": reg.erp_service,
                    "erp_fn": reg.erp_fn,
                    "policy_action": reg.policy_action,
                    "requires_approval": reg.requires_approval,
                    "allowed_roles": list(reg.allowed_roles),
                    "max_attempts": reg.max_attempts,
                    "idempotent": reg.idempotent,
                    "description": reg.description,
                    "required_payload_keys": list(reg.required_payload_keys),
                    "tags": list(reg.tags),
                }
            )
        return sorted(out, key=lambda x: x["name"])

    def names(self) -> list[str]:
        return sorted({r.name for r in self._by_name.values()})


command_registry = CommandRegistry()
