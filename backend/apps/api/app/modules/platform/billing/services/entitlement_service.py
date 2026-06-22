from __future__ import annotations

from app.modules.platform.billing.exceptions import FeatureNotEntitled
from app.modules.platform.billing.repositories.billing_repository import billing_repository
from app.modules.platform.billing.services.plan_service import plan_service
from app.modules.platform.billing.services.subscription_service import subscription_service


class EntitlementService:
    def schema_ready(self) -> bool:
        return billing_repository.schema_ready()

    def has_feature(self, org_id: str, feature_code: str) -> bool:
        if not self.schema_ready():
            plan_key = subscription_service.get_plan_key(org_id)
            return feature_code in plan_service.get_plan_features(plan_key)

        overrides = billing_repository.list_org_entitlement_overrides(org_id)
        for ov in overrides:
            if ov["feature_code"] == feature_code:
                return bool(ov["enabled"])

        plan_key = subscription_service.get_plan_key(org_id)
        features = plan_service.get_plan_features(plan_key)
        return feature_code in features

    def require_feature(self, org_id: str, feature_code: str) -> None:
        if not self.has_feature(org_id, feature_code):
            plan_key = subscription_service.get_plan_key(org_id)
            raise FeatureNotEntitled(feature_code, plan_key)

    def set_override(
        self,
        org_id: str,
        feature_code: str,
        *,
        enabled: bool,
        expires_at=None,
    ) -> dict:
        return billing_repository.upsert_org_entitlement(
            org_id,
            feature_code=feature_code,
            enabled=enabled,
            expires_at=expires_at,
        )


entitlement_service = EntitlementService()
