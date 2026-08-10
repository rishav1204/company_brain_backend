"""Error taxonomy for ERP Command Bridge — stable codes for handlers & clients."""

from __future__ import annotations

from enum import Enum


class ErrorClass(str, Enum):
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    BUSINESS_RULE = "business_rule"
    ERP_FAILURE = "erp_failure"
    WORKFLOW = "workflow"
    INFRASTRUCTURE = "infrastructure"
    TIMEOUT = "timeout"
    DUPLICATE = "duplicate"
    IDEMPOTENCY = "idempotency"
    APPROVAL = "approval"
    NOT_REGISTERED = "not_registered"
    UNKNOWN = "unknown"


class ErrorCode(str, Enum):
    ACCESS_DENIED = "ACCESS_DENIED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    ERP_CALL_FAILED = "ERP_CALL_FAILED"
    ERP_NOT_ALLOWLISTED = "ERP_NOT_ALLOWLISTED"
    WORKFLOW_FAILURE = "WORKFLOW_FAILURE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    TIMEOUT = "TIMEOUT"
    DUPLICATE_COMMAND = "DUPLICATE_COMMAND"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    COMMAND_NOT_REGISTERED = "COMMAND_NOT_REGISTERED"
    QUERY_NOT_REGISTERED = "QUERY_NOT_REGISTERED"
    PORT_NOT_REGISTERED = "PORT_NOT_REGISTERED"
    PORT_TIMEOUT = "PORT_TIMEOUT"
    UNKNOWN = "UNKNOWN"


# Default retryability by class
RETRYABLE_CLASSES = frozenset(
    {
        ErrorClass.INFRASTRUCTURE,
        ErrorClass.TIMEOUT,
        ErrorClass.ERP_FAILURE,  # may be retriable; handler may override
    }
)
