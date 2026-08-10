from __future__ import annotations

from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand
from app.modules.finance_os.bridges.erp_command_bridge.exceptions import CommandApprovalRequired


def ensure_approval(command: ErpCommand, *, requires_approval: bool) -> None:
    """
    Integrate with existing policy/workflow gates.
    Tool layer may already return pending_approval; bridge re-checks for direct callers.
    """
    if requires_approval and not command.human_approved:
        raise CommandApprovalRequired(
            "approval_required",
            draft=dict(command.payload or {}),
            policy_action=command.policy_action or command.command_type,
        )
    # Policy engine (non-tool path)
    if not command.human_approved and command.policy_action:
        try:
            from app.services.policy_service import requires_human_approval

            if requires_human_approval(
                org_id=command.org_id,
                action=command.policy_action,
                attrs=dict(command.attrs or {}),
                roles=list(command.roles),
            ):
                raise CommandApprovalRequired(
                    "approval_required",
                    draft=dict(command.payload or {}),
                    policy_action=command.policy_action,
                )
        except CommandApprovalRequired:
            raise
        except Exception:
            # Policy service optional / signature variance — do not invent new workflow engine
            pass
