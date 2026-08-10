from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.modules.finance_os.bridges.erp_command_bridge.contracts.lifecycle import CommandLifecycle


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ErpCommand:
    """
    Immutable, versionable ERP mutation command DTO (serialization-friendly).

    Prefer building a CommandContext and dispatching via CommandRegistry rather than
    inventing call paths that bypass the registry.
    """

    command_type: str
    org_id: str
    actor_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    command_id: str = field(default_factory=lambda: str(uuid4()))
    version: str = "v1"
    company_id: str | None = None
    idempotency_key: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    roles: tuple[str, ...] = ()
    attrs: dict[str, Any] = field(default_factory=dict)
    human_approved: bool = False
    policy_action: str | None = None
    # Optional ERP dispatch triple — registry may supply when omitted
    erp_module: str | None = None
    erp_service: str | None = None
    erp_fn: str | None = None
    org_style: str = "first"  # first | kw
    tool: str | None = None
    method: str | None = None
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def stable_hash_material(self) -> dict[str, Any]:
        """Fields used for idempotent request hashing (exclude random IDs/times)."""
        return {
            "command_type": self.command_type,
            "org_id": self.org_id,
            "actor_id": self.actor_id,
            "payload": self.payload,
            "company_id": self.company_id,
            "version": self.version,
            "erp_module": self.erp_module,
            "erp_service": self.erp_service,
            "erp_fn": self.erp_fn,
            "policy_action": self.policy_action,
        }


@dataclass(frozen=True)
class ErpCommandResult:
    status: str  # completed | failed | pending_approval | denied | duplicate
    command_id: str
    result: Any = None
    detail: str | None = None
    policy_action: str | None = None
    entity_id: str | None = None
    retryable: bool = False
    error_code: str | None = None
    error_class: str | None = None
    lifecycle: str = CommandLifecycle.EXECUTED.value
    duration_ms: float | None = None
    attempt: int = 1
    correlation_id: str | None = None
    from_cache: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Back-compat aliases
BaseCommand = ErpCommand
BaseResult = ErpCommandResult
