"""Command contexts — formal envelopes around DTO execution."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.modules.finance_os.bridges.erp_command_bridge.contracts.lifecycle import CommandLifecycle


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuthorizationContext:
    user_id: str
    roles: tuple[str, ...] = ()
    attrs: dict[str, Any] = field(default_factory=dict)
    company_id: str | None = None
    branch_id: str | None = None
    human_approved: bool = False
    action: str | None = None
    decision: str | None = None  # allow | deny
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApprovalContext:
    required: bool = False
    approved: bool = False
    approval_id: str | None = None
    workflow_id: str | None = None
    policy_action: str | None = None
    skip_gate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionContext:
    """Runtime execution metadata — not a business DTO."""

    lifecycle: CommandLifecycle = CommandLifecycle.REQUESTED
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None
    duration_ms: float | None = None
    attempt: int = 1
    max_attempts: int = 1
    erp_module: str | None = None
    erp_service: str | None = None
    erp_fn: str | None = None
    org_style: str = "first"
    entity_id: str | None = None
    error_code: str | None = None
    error_class: str | None = None
    retryable: bool = False
    transaction_boundary: str = "erp_service_owned"  # see docs
    outbox_enrolled: bool = False

    def mark(self, state: CommandLifecycle) -> None:
        self.lifecycle = state
        if state in {
            CommandLifecycle.EXECUTED,
            CommandLifecycle.FAILED,
            CommandLifecycle.REJECTED,
            CommandLifecycle.DUPLICATE,
            CommandLifecycle.APPROVAL_PENDING,
            CommandLifecycle.ROLLED_BACK,
        }:
            self.finished_at = _now()
            try:
                t0 = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(self.finished_at.replace("Z", "+00:00"))
                self.duration_ms = round((t1 - t0).total_seconds() * 1000.0, 2)
            except Exception:
                self.duration_ms = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["lifecycle"] = self.lifecycle.value
        return d


@dataclass
class CommandContext:
    """
    Full formal envelope for one bridge execution.

    ErpCommand (DTO) + AuthorizationContext + ApprovalContext + ExecutionContext.
    """

    command: Any  # ErpCommand — avoid circular import type
    authorization: AuthorizationContext
    approval: ApprovalContext
    execution: ExecutionContext
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    request_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command.to_dict() if hasattr(self.command, "to_dict") else {},
            "authorization": self.authorization.to_dict(),
            "approval": self.approval.to_dict(),
            "execution": self.execution.to_dict(),
            "correlation_id": self.correlation_id,
            "request_hash": self.request_hash,
        }
