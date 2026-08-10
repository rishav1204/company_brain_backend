"""Runtime failure taxonomy for M38 execution reliability (Phase 8 Wave 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FailureClass(str, Enum):
    VALIDATION = "ValidationFailure"
    PERMISSION = "PermissionFailure"
    POLICY = "PolicyFailure"
    TOOL = "ToolFailure"
    RETRIEVAL = "RetrievalFailure"
    TIMEOUT = "TimeoutFailure"
    DEPENDENCY = "DependencyFailure"
    EXTERNAL = "ExternalServiceFailure"
    PLANNER = "PlannerFailure"
    EXECUTION = "ExecutionFailure"
    COMPENSATION = "CompensationFailure"
    ENTITY_RESOLUTION = "EntityResolutionFailure"
    APPROVAL = "ApprovalRequired"
    UNKNOWN = "UnknownFailure"


@dataclass
class ClassifiedFailure:
    failure_class: FailureClass
    code: str
    message: str
    retryable: bool = False
    recoverable: bool = False
    node_id: str | None = None
    tool: str | None = None
    method: str | None = None
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "failure_class": self.failure_class.value,
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "recoverable": self.recoverable,
            "node_id": self.node_id,
            "tool": self.tool,
            "method": self.method,
            "details": self.details,
        }


def classify_tool_result(result: dict, *, node_id: str | None = None, tool: str | None = None, method: str | None = None) -> ClassifiedFailure | None:
    status = str(result.get("status") or "").lower()
    if status in {"completed", "success", ""} and not result.get("detail"):
        if status in {"completed", "success"}:
            return None
    if status in {"completed", "success"}:
        return None

    detail = str(result.get("detail") or result.get("message") or result.get("reason") or status or "unknown")
    detail_l = detail.lower()
    code = str(result.get("policy_code") or result.get("code") or status or "error")
    retryable = bool(result.get("retryable"))

    if status == "pending_approval" or "approval" in detail_l:
        return ClassifiedFailure(
            FailureClass.APPROVAL,
            code="APPROVAL_REQUIRED",
            message=detail,
            retryable=False,
            recoverable=True,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "forbidden" in detail_l or code in {"FORBIDDEN_ACTION", "TOOL_NOT_ALLOWED"}:
        return ClassifiedFailure(
            FailureClass.POLICY,
            code=code or "FORBIDDEN",
            message=detail,
            retryable=False,
            recoverable=False,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "policy" in detail_l or "abac" in detail_l or code in {"POLICY_DENIED", "GOVERNANCE_DENIED"}:
        return ClassifiedFailure(
            FailureClass.POLICY,
            code=code or "POLICY_DENIED",
            message=detail,
            retryable=False,
            recoverable=True,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "permission" in detail_l or "unauthorized" in detail_l or "denied" in detail_l:
        return ClassifiedFailure(
            FailureClass.PERMISSION,
            code=code or "PERMISSION_DENIED",
            message=detail,
            retryable=False,
            recoverable=False,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "timeout" in detail_l or "timed out" in detail_l:
        return ClassifiedFailure(
            FailureClass.TIMEOUT,
            code="TIMEOUT",
            message=detail,
            retryable=True,
            recoverable=True,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "validation" in detail_l or "invalid" in detail_l or "missing required" in detail_l:
        return ClassifiedFailure(
            FailureClass.VALIDATION,
            code=code or "VALIDATION_ERROR",
            message=detail,
            retryable=False,
            recoverable=False,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "retrieval" in detail_l:
        return ClassifiedFailure(
            FailureClass.RETRIEVAL,
            code="RETRIEVAL_FAILED",
            message=detail,
            retryable=True,
            recoverable=True,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if "compensation" in detail_l or "undo" in detail_l:
        return ClassifiedFailure(
            FailureClass.COMPENSATION,
            code="COMPENSATION_FAILED",
            message=detail,
            retryable=False,
            recoverable=False,
            node_id=node_id,
            tool=tool,
            method=method,
        )
    if status == "error" or not status:
        return ClassifiedFailure(
            FailureClass.TOOL if tool else FailureClass.EXECUTION,
            code=code or "TOOL_ERROR",
            message=detail,
            retryable=retryable if "retryable" in result else True,
            recoverable=True,
            node_id=node_id,
            tool=tool,
            method=method,
            details={"raw_status": status},
        )
    return ClassifiedFailure(
        FailureClass.UNKNOWN,
        code=code or "UNKNOWN",
        message=detail,
        retryable=retryable,
        recoverable=False,
        node_id=node_id,
        tool=tool,
        method=method,
    )


def classify_exception(exc: BaseException, *, context: str = "execution") -> ClassifiedFailure:
    msg = str(exc) or type(exc).__name__
    msg_l = msg.lower()
    if "timeout" in msg_l:
        fc = FailureClass.TIMEOUT
    elif isinstance(exc, ValueError):
        fc = FailureClass.VALIDATION
    elif "permission" in msg_l or "denied" in msg_l:
        fc = FailureClass.PERMISSION
    elif context == "retrieval":
        fc = FailureClass.RETRIEVAL
    elif context == "planner":
        fc = FailureClass.PLANNER
    elif context == "compensation":
        fc = FailureClass.COMPENSATION
    else:
        fc = FailureClass.EXECUTION
    return ClassifiedFailure(
        failure_class=fc,
        code=type(exc).__name__,
        message=msg,
        retryable=fc in {FailureClass.TIMEOUT, FailureClass.RETRIEVAL, FailureClass.DEPENDENCY, FailureClass.EXTERNAL},
        recoverable=fc not in {FailureClass.PERMISSION, FailureClass.POLICY},
        details={"context": context},
    )
