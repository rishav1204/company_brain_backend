from __future__ import annotations

from app.modules.finance_os.bridges.erp_command_bridge.contracts.errors import ErrorClass, ErrorCode


class BridgeError(Exception):
    """Base command bridge error with taxonomy."""

    error_class: ErrorClass = ErrorClass.UNKNOWN
    error_code: ErrorCode = ErrorCode.UNKNOWN
    retryable: bool = False

    def __init__(self, message: str, *, retryable: bool | None = None, error_code: ErrorCode | None = None):
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable
        if error_code is not None:
            self.error_code = error_code


class CommandValidationError(BridgeError, ValueError):
    error_class = ErrorClass.VALIDATION
    error_code = ErrorCode.VALIDATION_FAILED
    retryable = False


class CommandAuthorizationError(BridgeError, PermissionError):
    error_class = ErrorClass.AUTHORIZATION
    error_code = ErrorCode.ACCESS_DENIED
    retryable = False


class CommandApprovalRequired(BridgeError):
    error_class = ErrorClass.APPROVAL
    error_code = ErrorCode.APPROVAL_REQUIRED
    retryable = False

    def __init__(
        self,
        message: str = "approval_required",
        *,
        draft: dict | None = None,
        policy_action: str | None = None,
    ):
        super().__init__(message, retryable=False, error_code=ErrorCode.APPROVAL_REQUIRED)
        self.draft = draft or {}
        self.policy_action = policy_action


class CommandExecutionError(BridgeError):
    error_class = ErrorClass.ERP_FAILURE
    error_code = ErrorCode.ERP_CALL_FAILED
    retryable = True


class BusinessRuleError(BridgeError, ValueError):
    error_class = ErrorClass.BUSINESS_RULE
    error_code = ErrorCode.BUSINESS_RULE_VIOLATION
    retryable = False


class InfrastructureError(BridgeError):
    error_class = ErrorClass.INFRASTRUCTURE
    error_code = ErrorCode.INFRASTRUCTURE_FAILURE
    retryable = True


class TimeoutBridgeError(BridgeError):
    error_class = ErrorClass.TIMEOUT
    error_code = ErrorCode.TIMEOUT
    retryable = True


class DuplicateCommandError(BridgeError):
    error_class = ErrorClass.DUPLICATE
    error_code = ErrorCode.DUPLICATE_COMMAND
    retryable = False

    def __init__(self, message: str = "duplicate_command", *, cached_result: dict | None = None):
        super().__init__(message, retryable=False, error_code=ErrorCode.DUPLICATE_COMMAND)
        self.cached_result = cached_result or {}


class IdempotencyError(BridgeError):
    error_class = ErrorClass.IDEMPOTENCY
    error_code = ErrorCode.IDEMPOTENCY_CONFLICT
    retryable = False


class CommandNotRegisteredError(BridgeError):
    error_class = ErrorClass.NOT_REGISTERED
    error_code = ErrorCode.COMMAND_NOT_REGISTERED
    retryable = False


class CommandTargetNotAllowlisted(BridgeError, PermissionError):
    error_class = ErrorClass.AUTHORIZATION
    error_code = ErrorCode.ERP_NOT_ALLOWLISTED
    retryable = False


class WorkflowBridgeError(BridgeError):
    error_class = ErrorClass.WORKFLOW
    error_code = ErrorCode.WORKFLOW_FAILURE
    retryable = False


def classify_exception(exc: BaseException) -> tuple[ErrorClass, ErrorCode, bool]:
    if isinstance(exc, BridgeError):
        return exc.error_class, exc.error_code, bool(exc.retryable)
    if isinstance(exc, PermissionError):
        return ErrorClass.AUTHORIZATION, ErrorCode.ACCESS_DENIED, False
    if isinstance(exc, ValueError):
        return ErrorClass.BUSINESS_RULE, ErrorCode.BUSINESS_RULE_VIOLATION, False
    if isinstance(exc, TimeoutError):
        return ErrorClass.TIMEOUT, ErrorCode.TIMEOUT, True
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return ErrorClass.TIMEOUT, ErrorCode.TIMEOUT, True
    if "connection" in name or "operational" in name:
        return ErrorClass.INFRASTRUCTURE, ErrorCode.INFRASTRUCTURE_FAILURE, True
    return ErrorClass.ERP_FAILURE, ErrorCode.ERP_CALL_FAILED, True
