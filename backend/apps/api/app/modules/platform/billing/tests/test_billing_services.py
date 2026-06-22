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
