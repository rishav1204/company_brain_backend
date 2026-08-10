from app.core.request_context import RequestContext
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access, resolve_required_scope
import pytest
from fastapi import HTTPException


def test_resolve_scope_from_action() -> None:
    assert resolve_required_scope(action="approve_payment", object_type="workflow", mode="write") == "payment.approve"


def test_api_key_scope_denied() -> None:
    ctx = RequestContext(
        request_id="r1",
        org_id="org",
        user_id="apikey:1",
        roles=["api_integration"],
        auth_method="api_key",
        api_key_scopes=["invoice.read"],
    )
    with pytest.raises(HTTPException) as exc:
        enforce_finance_route_access(ctx, action="approve_payment", object_type="workflow", mode="write")
    assert exc.value.status_code == 403


def test_api_key_scope_denied_for_wildcard() -> None:
    ctx = RequestContext(
        request_id="r1",
        org_id="org",
        user_id="apikey:1",
        roles=["api_integration"],
        auth_method="api_key",
        api_key_scopes=["*"],
    )
    with pytest.raises(HTTPException) as exc:
        enforce_finance_route_access(ctx, action="approve_payment", object_type="workflow", mode="write")
    assert exc.value.status_code == 403
