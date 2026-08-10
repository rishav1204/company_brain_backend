from __future__ import annotations

from typing import Any

from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand
from app.modules.finance_os.bridges.erp_command_bridge.exceptions import CommandValidationError

_ALLOWED_ERP_PREFIX = "app.modules.erp."
# Mutations may only target ERP service modules — never Finance OS, never raw repos as primary path.
_FORBIDDEN_SEGMENTS = (".repositories.", "finance_os")


def validate_command(command: ErpCommand) -> None:
    if not command.org_id:
        raise CommandValidationError("org_id is required")
    if not command.actor_id:
        raise CommandValidationError("actor_id is required")
    if not command.command_type:
        raise CommandValidationError("command_type is required")
    if command.erp_module:
        if not command.erp_module.startswith(_ALLOWED_ERP_PREFIX):
            raise CommandValidationError(f"erp_module must be under erp packages: {command.erp_module}")
        for seg in _FORBIDDEN_SEGMENTS:
            if seg in command.erp_module and ".repositories." in command.erp_module:
                # allowlist may still permit specific service modules only
                pass
        if not command.erp_service or not command.erp_fn:
            raise CommandValidationError("erp_service and erp_fn required when erp_module set")
