from __future__ import annotations

from typing import Any

from app.modules.finance_os.bridges.erp_command_bridge.approval.approval_gate import ensure_approval
from app.modules.finance_os.bridges.erp_command_bridge.authorization.authz import authorize_command
from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import (
    ErpCommand,
    ErpCommandResult,
)
from app.modules.finance_os.bridges.erp_command_bridge.contracts.contexts import (
    ApprovalContext,
    AuthorizationContext,
    CommandContext,
    ExecutionContext,
)
from app.modules.finance_os.bridges.erp_command_bridge.contracts.lifecycle import CommandLifecycle
from app.modules.finance_os.bridges.erp_command_bridge.events import command_events
from app.modules.finance_os.bridges.erp_command_bridge.exceptions import (
    BridgeError,
    CommandApprovalRequired,
    CommandAuthorizationError,
    CommandExecutionError,
    CommandNotRegisteredError,
    CommandValidationError,
    classify_exception,
)
from app.modules.finance_os.bridges.erp_command_bridge.handlers.erp_dispatch import dispatch_erp_call
from app.modules.finance_os.bridges.erp_command_bridge.idempotency.strategy import (
    check_idempotent,
    request_hash,
    store_idempotent,
)
from app.modules.finance_os.bridges.erp_command_bridge.observability.command_log import log_command
from app.modules.finance_os.bridges.erp_command_bridge.registry.command_registry import (
    CommandRegistration,
    command_registry,
)
from app.modules.finance_os.bridges.erp_command_bridge.retry.policy import RetryPolicy, run_with_retry
from app.modules.finance_os.bridges.erp_command_bridge.validators.command_validator import validate_command


def _entity_id_from(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    if result.get("id"):
        return str(result["id"])
    for key in ("invoice", "journal", "voucher", "po", "payment", "vendor", "customer"):
        nested = result.get(key)
        if isinstance(nested, dict) and nested.get("id"):
            return str(nested["id"])
    for key in ("invoice_id", "journal_id", "voucher_id", "entity_id"):
        if result.get(key):
            return str(result[key])
    return None


def _build_context(
    command: ErpCommand,
    *,
    registration: CommandRegistration | None,
    requires_approval: bool,
    skip_approval_gate: bool,
) -> CommandContext:
    reg = registration
    auth = AuthorizationContext(
        user_id=command.actor_id,
        roles=command.roles,
        attrs=dict(command.attrs or {}),
        company_id=command.company_id,
        branch_id=(command.attrs or {}).get("branch_id") if isinstance(command.attrs, dict) else None,
        human_approved=command.human_approved,
        action=command.policy_action or (reg.policy_action if reg else None) or command.command_type,
    )
    approval = ApprovalContext(
        required=requires_approval if requires_approval else bool(reg.requires_approval if reg else False),
        approved=command.human_approved,
        approval_id=(command.attrs or {}).get("approval_id") if isinstance(command.attrs, dict) else None,
        workflow_id=(command.attrs or {}).get("workflow_id") if isinstance(command.attrs, dict) else None,
        policy_action=command.policy_action or (reg.policy_action if reg else None),
        skip_gate=skip_approval_gate,
    )
    execution = ExecutionContext(
        lifecycle=CommandLifecycle.REQUESTED,
        max_attempts=reg.max_attempts if reg else 1,
        erp_module=command.erp_module or (reg.erp_module if reg else None),
        erp_service=command.erp_service or (reg.erp_service if reg else None),
        erp_fn=command.erp_fn or (reg.erp_fn if reg else None),
        org_style=command.org_style or (reg.org_style if reg else "first"),
        transaction_boundary="erp_service_owned",
    )
    return CommandContext(
        command=command,
        authorization=auth,
        approval=approval,
        execution=execution,
        correlation_id=command.correlation_id or command.command_id,
        request_hash=request_hash(command.stable_hash_material()),
    )


def _enrich_command_from_registry(command: ErpCommand, reg: CommandRegistration) -> ErpCommand:
    """Return command with ERP target filled from registration when missing."""
    if command.erp_module and command.erp_service and command.erp_fn:
        return command
    # frozen dataclass — rebuild
    return ErpCommand(
        command_type=command.command_type,
        org_id=command.org_id,
        actor_id=command.actor_id,
        payload=command.payload,
        command_id=command.command_id,
        version=command.version,
        company_id=command.company_id,
        idempotency_key=command.idempotency_key,
        correlation_id=command.correlation_id,
        trace_id=command.trace_id,
        roles=command.roles,
        attrs=command.attrs,
        human_approved=command.human_approved,
        policy_action=command.policy_action or reg.policy_action,
        erp_module=command.erp_module or reg.erp_module,
        erp_service=command.erp_service or reg.erp_service,
        erp_fn=command.erp_fn or reg.erp_fn,
        org_style=command.org_style or reg.org_style,
        tool=command.tool,
        method=command.method,
        created_at=command.created_at,
    )


def _role_check(command: ErpCommand, reg: CommandRegistration | None) -> None:
    if not reg or not reg.allowed_roles:
        return
    actor_roles = {str(r).lower() for r in command.roles}
    allowed = {str(r).lower() for r in reg.allowed_roles}
    if actor_roles and not (actor_roles & allowed):
        # empty roles often system paths — only enforce when roles provided
        if command.roles:
            raise CommandAuthorizationError(f"role_not_allowed:{sorted(allowed)}")


def _payload_required(command: ErpCommand, reg: CommandRegistration | None) -> None:
    if not reg or not reg.required_payload_keys:
        return
    missing = [k for k in reg.required_payload_keys if k not in (command.payload or {})]
    if missing:
        raise CommandValidationError(f"Missing payload keys: {', '.join(missing)}")


class ErpCommandService:
    """
    Anti-corruption layer entrypoint (Command Registry driven).

    Rules (see PERFORMANCE_RULES.py):
    - no business logic, no SQL, no repository access
    - register commands; resolve via registry; dispatch allowlisted ERP services only
    - Transaction boundary: ERP service owns its DB TX; platform outbox enrolled by ERP/event_service
    """

    def execute(
        self,
        command: ErpCommand,
        *,
        requires_approval: bool = False,
        skip_approval_gate: bool = False,
        skip_authz_on_human_approved: bool = False,
    ) -> ErpCommandResult:
        reg = command_registry.get_optional(command.command_type)
        if reg is None and command.tool and command.method:
            reg = command_registry.get_by_tool(command.tool, command.method)
        if reg is not None:
            command = _enrich_command_from_registry(command, reg)

        ctx = _build_context(
            command,
            registration=reg,
            requires_approval=requires_approval,
            skip_approval_gate=skip_approval_gate,
        )

        log_command(
            "erp.command.lifecycle",
            command_id=command.command_id,
            command_type=command.command_type,
            org_id=command.org_id,
            actor_id=command.actor_id,
            lifecycle=CommandLifecycle.REQUESTED.value,
            correlation_id=ctx.correlation_id,
            company_id=command.company_id,
            erp_module=ctx.execution.erp_module,
            erp_service=ctx.execution.erp_service,
            erp_fn=ctx.execution.erp_fn,
            approval_id=ctx.approval.approval_id,
            workflow_id=ctx.approval.workflow_id,
        )
        command_events.emit_requested(command)

        # Idempotency / duplicate
        idem_key = command.idempotency_key or (
            f"{command.command_type}:{ctx.request_hash}" if (reg and reg.idempotent) else None
        )
        material = command.stable_hash_material()
        cached = check_idempotent(command.org_id, idem_key, material)
        if cached is not None:
            ctx.execution.mark(CommandLifecycle.DUPLICATE)
            command_events.emit_duplicate(command, cached=cached)
            log_command(
                "erp.command.duplicate",
                command_id=command.command_id,
                command_type=command.command_type,
                org_id=command.org_id,
                actor_id=command.actor_id,
                status="duplicate",
                lifecycle=CommandLifecycle.DUPLICATE.value,
                correlation_id=ctx.correlation_id,
                error_code="DUPLICATE_COMMAND",
            )
            return ErpCommandResult(
                status="duplicate",
                command_id=command.command_id,
                result=cached.get("result", cached),
                detail="duplicate_command",
                lifecycle=CommandLifecycle.DUPLICATE.value,
                correlation_id=ctx.correlation_id,
                from_cache=True,
                error_code="DUPLICATE_COMMAND",
                error_class="duplicate",
            )

        try:
            validate_command(command)
            _payload_required(command, reg)
            if reg and reg.validator:
                reg.validator(command)
            ctx.execution.mark(CommandLifecycle.VALIDATED)

            ctx.execution.mark(CommandLifecycle.AUTHORIZING)
            _role_check(command, reg)
            try:
                authorize_command(command)
                ctx.authorization.decision = "allow"
                ctx.execution.mark(CommandLifecycle.AUTHORIZED)
            except CommandAuthorizationError:
                if skip_authz_on_human_approved and command.human_approved:
                    ctx.authorization.decision = "allow_soft"
                    ctx.execution.mark(CommandLifecycle.AUTHORIZED)
                else:
                    raise

            if not ctx.approval.skip_gate:
                try:
                    ensure_approval(command, requires_approval=ctx.approval.required)
                except CommandApprovalRequired:
                    ctx.execution.mark(CommandLifecycle.APPROVAL_PENDING)
                    command_events.emit_approval_pending(command)
                    log_command(
                        "erp.command.approval_pending",
                        command_id=command.command_id,
                        command_type=command.command_type,
                        org_id=command.org_id,
                        actor_id=command.actor_id,
                        status="pending_approval",
                        lifecycle=CommandLifecycle.APPROVAL_PENDING.value,
                        correlation_id=ctx.correlation_id,
                        error_code="APPROVAL_REQUIRED",
                    )
                    return ErpCommandResult(
                        status="pending_approval",
                        command_id=command.command_id,
                        detail="approval_required",
                        policy_action=ctx.approval.policy_action,
                        result={"draft": dict(command.payload or {})},
                        lifecycle=CommandLifecycle.APPROVAL_PENDING.value,
                        correlation_id=ctx.correlation_id,
                        error_code="APPROVAL_REQUIRED",
                        error_class="approval",
                    )
            if command.human_approved:
                ctx.approval.approved = True
                ctx.execution.mark(CommandLifecycle.APPROVED)
                command_events.emit_approved(command)

            if not ctx.execution.erp_module or not ctx.execution.erp_service or not ctx.execution.erp_fn:
                # Unregistered ad-hoc target is only allowed if already on mutation allowlist
                if not command.erp_module:
                    raise CommandNotRegisteredError(
                        f"command_not_registered:{command.command_type} (register in CommandRegistry)"
                    )
                ctx.execution.erp_module = command.erp_module
                ctx.execution.erp_service = command.erp_service
                ctx.execution.erp_fn = command.erp_fn

            ctx.execution.mark(CommandLifecycle.EXECUTING)
            policy = RetryPolicy(max_attempts=max(1, ctx.execution.max_attempts))

            def _call() -> Any:
                return dispatch_erp_call(
                    command.org_id,
                    module=str(ctx.execution.erp_module),
                    service=str(ctx.execution.erp_service),
                    fn=str(ctx.execution.erp_fn),
                    kwargs=dict(command.payload or {}),
                    org_style=ctx.execution.org_style,
                )

            # TX boundary: ERP service owns commit; bridge does not open SQL or run business logic.
            # Side-effect events go through platform_event_service → transactional outbox when schema ready.
            ctx.execution.outbox_enrolled = True
            raw = run_with_retry(_call, policy=policy)
            eid = _entity_id_from(raw)
            ctx.execution.entity_id = eid
            ctx.execution.mark(CommandLifecycle.EXECUTED)
            command_events.emit_executed(command, entity_id=eid)

            result = ErpCommandResult(
                status="completed",
                command_id=command.command_id,
                result=raw,
                entity_id=eid,
                policy_action=command.policy_action,
                lifecycle=CommandLifecycle.EXECUTED.value,
                duration_ms=ctx.execution.duration_ms,
                attempt=ctx.execution.attempt,
                correlation_id=ctx.correlation_id,
            )
            store_idempotent(
                command.org_id,
                idem_key,
                material,
                result.to_dict(),
            )
            log_command(
                "erp.command.executed",
                command_id=command.command_id,
                command_type=command.command_type,
                org_id=command.org_id,
                actor_id=command.actor_id,
                status="completed",
                lifecycle=CommandLifecycle.EXECUTED.value,
                duration_ms=ctx.execution.duration_ms,
                erp_module=ctx.execution.erp_module,
                erp_service=ctx.execution.erp_service,
                erp_fn=ctx.execution.erp_fn,
                entity_id=eid,
                correlation_id=ctx.correlation_id,
                company_id=command.company_id,
                attempt=ctx.execution.attempt,
            )
            return result

        except CommandApprovalRequired as exc:
            ctx.execution.mark(CommandLifecycle.APPROVAL_PENDING)
            return ErpCommandResult(
                status="pending_approval",
                command_id=command.command_id,
                detail=str(exc),
                policy_action=exc.policy_action or command.policy_action,
                result={"draft": exc.draft},
                lifecycle=CommandLifecycle.APPROVAL_PENDING.value,
                correlation_id=ctx.correlation_id,
                error_code="APPROVAL_REQUIRED",
                error_class="approval",
            )
        except CommandAuthorizationError as exc:
            ctx.execution.mark(CommandLifecycle.REJECTED)
            command_events.emit_rejected(command, reason=str(exc))
            return self._fail_result(command, ctx, exc, status="denied", lifecycle=CommandLifecycle.REJECTED)
        except Exception as exc:
            ctx.execution.mark(CommandLifecycle.FAILED)
            command_events.emit_failed(command, reason=str(exc))
            return self._fail_result(command, ctx, exc, status="failed", lifecycle=CommandLifecycle.FAILED)

    def _fail_result(
        self,
        command: ErpCommand,
        ctx: CommandContext,
        exc: BaseException,
        *,
        status: str,
        lifecycle: CommandLifecycle,
    ) -> ErpCommandResult:
        err_class, err_code, retryable = classify_exception(exc)
        if isinstance(exc, BridgeError):
            detail = str(exc)
        elif isinstance(exc, ValueError):
            detail = str(exc)
            retryable = False
        else:
            detail = "command_execution_failed" if status == "failed" and not isinstance(exc, BridgeError) else str(exc)
            if not isinstance(exc, (BridgeError, ValueError, PermissionError)):
                detail = "command_execution_failed"
        ctx.execution.error_class = err_class.value
        ctx.execution.error_code = err_code.value
        ctx.execution.retryable = retryable
        log_command(
            "erp.command.failed",
            command_id=command.command_id,
            command_type=command.command_type,
            org_id=command.org_id,
            actor_id=command.actor_id,
            status=status,
            lifecycle=lifecycle.value,
            duration_ms=ctx.execution.duration_ms,
            correlation_id=ctx.correlation_id,
            error_code=err_code.value,
            error_class=err_class.value,
            erp_module=ctx.execution.erp_module,
            erp_service=ctx.execution.erp_service,
            erp_fn=ctx.execution.erp_fn,
            company_id=command.company_id,
        )
        return ErpCommandResult(
            status=status,
            command_id=command.command_id,
            detail=detail,
            policy_action=command.policy_action,
            retryable=retryable,
            error_code=err_code.value,
            error_class=err_class.value,
            lifecycle=lifecycle.value,
            duration_ms=ctx.execution.duration_ms,
            correlation_id=ctx.correlation_id,
        )

    def execute_tool_mutation(
        self,
        org_id: str,
        *,
        tool: str,
        method: str,
        erp_module: str,
        erp_service: str,
        erp_fn: str,
        kwargs: dict[str, Any],
        actor_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
        human_approved: bool = False,
        policy_action: str | None = None,
        requires_approval: bool = False,
        org_style: str = "first",
        skip_bridge_approval_gate: bool = True,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Path used by M38 tool_spec after tool-level policy already ran.
        Resolves CommandRegistry entry by tool.method when present.
        """
        command_type = f"{tool}.{method}"
        command = ErpCommand(
            command_type=command_type,
            org_id=org_id,
            actor_id=actor_id or "platform-runtime",
            payload=dict(kwargs or {}),
            roles=tuple(str(r) for r in (roles or [])),
            attrs=dict(attrs or {}),
            human_approved=human_approved,
            policy_action=policy_action or command_type,
            erp_module=erp_module,
            erp_service=erp_service,
            erp_fn=erp_fn,
            org_style=org_style,
            tool=tool,
            method=method,
            company_id=(attrs or {}).get("company_id") if isinstance(attrs, dict) else None,
            correlation_id=(attrs or {}).get("correlation_id") if isinstance(attrs, dict) else None,
            trace_id=(attrs or {}).get("trace_id") if isinstance(attrs, dict) else None,
            idempotency_key=idempotency_key
            or ((attrs or {}).get("idempotency_key") if isinstance(attrs, dict) else None),
        )
        result = self.execute(
            command,
            requires_approval=requires_approval,
            skip_approval_gate=skip_bridge_approval_gate,
            skip_authz_on_human_approved=True,
        )
        if result.status == "completed":
            return {
                "status": "completed",
                "target": tool,
                "detail": method,
                "policy_action": policy_action or command_type,
                "result": result.result,
                "entity_id": result.entity_id,
                "command_id": result.command_id,
                "lifecycle": result.lifecycle,
                "correlation_id": result.correlation_id,
                "duration_ms": result.duration_ms,
            }
        if result.status == "pending_approval":
            return {
                "status": "pending_approval",
                "detail": result.detail or "approval_required",
                "target": tool,
                "draft": (result.result or {}).get("draft") if isinstance(result.result, dict) else kwargs,
                "policy_action": result.policy_action,
                "command_id": result.command_id,
            }
        if result.status == "duplicate":
            return {
                "status": "completed",
                "target": tool,
                "detail": method,
                "policy_action": policy_action or command_type,
                "result": result.result,
                "command_id": result.command_id,
                "from_cache": True,
            }
        return {
            "status": "error",
            "detail": result.detail or result.status,
            "target": tool,
            "retryable": result.retryable,
            "policy_action": policy_action,
            "error_code": result.error_code,
            "error_class": result.error_class,
            "command_id": result.command_id,
            "lifecycle": result.lifecycle,
        }

    def create_voucher_from_extraction(
        self,
        org_id: str,
        *,
        extraction_id: str,
        actor_id: str | None = None,
    ) -> dict:
        command = ErpCommand(
            command_type="CreateVoucherFromExtraction",
            org_id=org_id,
            actor_id=actor_id or "invoice-ai-pipeline",
            payload={"extraction_id": extraction_id, "created_by": actor_id},
            policy_action="vouchers.create_from_extraction",
            human_approved=True,
            tool="vouchers",
            method="create_from_extraction",
            idempotency_key=f"CreateVoucherFromExtraction:{org_id}:{extraction_id}",
        )
        result = self.execute(command, requires_approval=False, skip_approval_gate=True)
        if result.status not in {"completed", "duplicate"}:
            raise ValueError(result.detail or result.status)
        raw = result.result
        return raw if isinstance(raw, dict) else {"result": raw}

    def register_command(self, registration: CommandRegistration, **kwargs: Any) -> None:
        """Extension point — prefer bootstrap modules calling command_registry.register."""
        command_registry.register(registration, **kwargs)


erp_command_service = ErpCommandService()
