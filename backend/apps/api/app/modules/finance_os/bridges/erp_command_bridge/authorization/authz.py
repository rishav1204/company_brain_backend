from __future__ import annotations

from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand
from app.modules.finance_os.bridges.erp_command_bridge.exceptions import CommandAuthorizationError
from app.services.object_context import ObjectContext


def authorize_command(command: ErpCommand) -> None:
    """Tenant + RBAC/ABAC gate before any ERP mutation from Finance OS."""
    action = command.policy_action or command.command_type
    object_context = ObjectContext(
        object_type=str((command.attrs or {}).get("object_type") or "erp_command"),
        object_id=str((command.attrs or {}).get("object_id") or command.command_id),
        company_id=command.company_id or (command.attrs or {}).get("company_id"),
        branch_id=(command.attrs or {}).get("branch_id"),
    )
    try:
        decision = evaluate_access(
            org_id=command.org_id,
            user_id=command.actor_id,
            roles=list(command.roles),
            action=action,
            object_context=object_context,
            attrs=dict(command.attrs or {}),
            human_approved=command.human_approved,
            object_company_id=command.company_id,
            emit_denial_event=True,
        )
    except Exception as exc:
        raise CommandAuthorizationError(f"authorization_failed:{exc}") from exc

    allowed = bool(getattr(decision, "allowed", True))
    reason = getattr(decision, "reason", None)
    if not allowed:
        raise CommandAuthorizationError(reason or "access_denied")
