from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.platform.billing.constants import PLAN_FEATURES, DEFAULT_PLAN_KEY
from app.modules.platform.billing.exceptions import FeatureNotEntitled, QuotaExceeded
from app.modules.platform.billing.services.entitlement_service import entitlement_service
from app.modules.platform.billing.services.plan_service import plan_service
from app.modules.platform.billing.services.usage_service import usage_service
from app.modules.platform.billing.services.credit_service import credit_service


ORG = "00000000-0000-4000-8000-000000000001"


def test_starter_plan_features() -> None:
    features = plan_service.get_plan_features("finance_starter")
    assert "ap" in features
    assert "invoice_ai" not in features


def test_pro_plan_has_invoice_ai() -> None:
    features = plan_service.get_plan_features("finance_os_pro")
    assert "invoice_ai" in features


def test_entitlement_denies_growth_feature_on_starter() -> None:
    with pytest.raises(FeatureNotEntitled):
        entitlement_service.require_feature(ORG, "procurement")


def test_quota_exceeded_raises() -> None:
    limit = plan_service.get_plan_limit("finance_starter", "max_users")
    assert limit == 5
    with pytest.raises(QuotaExceeded):
        usage_service.check_quota(ORG, "max_users", increment=999)


def test_credit_catalog() -> None:
    assert credit_service.operation_cost("invoice_ai_review") == 2.0
    assert credit_service.operation_cost("agent_execution") == 10.0


def test_default_plan_key() -> None:
    assert DEFAULT_PLAN_KEY in PLAN_FEATURES


def test_admin_billing_routes_require_platform_admin() -> None:
    """Assigning plans / granting credits targets any org_id in the body.
    That must never fall back to tenant_admin — otherwise any customer-org
    admin can escalate to full commercial control of every tenant.
    """
    from app.modules.core.iam.middleware.permission_guard import _TENANT_ADMIN_ALLOWED
    from app.modules.platform.billing.routes import admin_billing_routes

    assert "platform.admin" not in _TENANT_ADMIN_ALLOWED
    assert not hasattr(admin_billing_routes, "_require_tenant_admin")

    paths = {route.path for route in admin_billing_routes.router.routes}
    required = {
        "/admin/billing/plans",
        "/admin/billing/plans/{plan_key}",
        "/admin/billing/plans/{plan_key}/features",
        "/admin/billing/plans/{plan_key}/limits",
        "/admin/billing/subscriptions/assign",
        "/admin/billing/credits/grant",
        "/admin/billing/entitlements/override",
        "/admin/billing/orgs/{org_id}/disable-ai",
    }
    assert required.issubset(paths)

    expected = admin_billing_routes._PLATFORM_ADMIN
    for route in admin_billing_routes.router.routes:
        dep_calls = [dep.call for dep in route.dependant.dependencies]
        assert expected in dep_calls, f"{route.path} is not gated by platform.admin"


def test_plan_ceiling_requires_break_glass() -> None:
    from unittest.mock import patch

    with (
        patch(
            "app.modules.platform.billing.services.entitlement_service.subscription_service.get_plan_key",
            return_value="finance_starter",
        ),
        patch(
            "app.modules.platform.billing.services.entitlement_service.plan_service.get_plan_features",
            return_value={"ap", "ar", "coa"},
        ),
    ):
        with pytest.raises(ValueError, match="break_glass"):
            entitlement_service.set_override(ORG, "agents", enabled=True, break_glass=False)


def test_disable_ai_codes() -> None:
    assert "agents" in __import__(
        "app.modules.platform.billing.services.entitlement_service", fromlist=["AI_FEATURE_CODES"]
    ).AI_FEATURE_CODES
