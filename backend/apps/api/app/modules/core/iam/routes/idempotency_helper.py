from collections.abc import Callable

from fastapi import HTTPException

from app.core.request_context import RequestContext
from app.services.iam_idempotency import iam_idempotency_service


def check_idempotency(scope: str, context: RequestContext, idempotency_key: str | None) -> None:
    if not idempotency_key:
        return
    if iam_idempotency_service.is_replay(scope, context.org_id, idempotency_key):
        raise HTTPException(status_code=409, detail="Idempotent replay: request already processed")


def mark_idempotency(scope: str, context: RequestContext, idempotency_key: str | None) -> None:
    if idempotency_key:
        iam_idempotency_service.mark(scope, context.org_id, idempotency_key)


def idempotent_handler(
    scope: str,
    context: RequestContext,
    idempotency_key: str | None,
    handler: Callable[[], dict],
) -> dict:
    check_idempotency(scope, context, idempotency_key)
    result = handler()
    mark_idempotency(scope, context, idempotency_key)
    return result
