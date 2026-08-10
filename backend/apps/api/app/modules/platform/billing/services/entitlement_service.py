from __future__ import annotations

from typing import Any

from app.modules.platform.billing.exceptions import FeatureNotEntitled
from app.modules.platform.billing.repositories.billing_repository import billing_repository
from app.modules.platform.billing.services.plan_service import plan_service
from app.modules.platform.billing.services.subscription_service import subscription_service

AI_FEATURE_CODES = frozenset(
    {
        "invoice_ai",
        "agents",
        "memory",
        "graph_engine",
        "workflow_intelligence",
        "forecasting",
    }
)


class EntitlementService:
    def schema_ready(self) -> bool:
        return billing_repository.schema_ready()

    def _catalog_codes(self) -> list[str]:
        from app.modules.platform.billing.constants import FEATURE_CODES

        try:
            from app.modules.platform.control_plane.repositories.control_plane_repository import (
                control_plane_repository,
            )

            codes = [
                r["feature_code"]
                for r in control_plane_repository.list_features()
                if r.get("status") in (None, "active")
            ]
            if codes:
                return codes
        except Exception:
            pass
        return list(FEATURE_CODES)

    def _snapshot(self, org_id: str) -> dict[str, Any]:
        """Load plan/overrides/controls once for bulk entitlement checks."""
        plan_key = subscription_service.get_plan_key(org_id)
        plan_features = set(plan_service.get_plan_features(plan_key))
        overrides: dict[str, bool] = {}
        if self.schema_ready():
            overrides = {
                str(o["feature_code"]): bool(o.get("enabled"))
                for o in billing_repository.list_org_entitlement_overrides(org_id)
            }
        controls: dict[str, Any] = {
            "lifecycle_status": "active",
            "login_allowed": True,
            "ai_enabled": True,
            "erp_modules_enabled": True,
            "api_access_allowed": True,
        }
        ai_codes = set(AI_FEATURE_CODES)
        try:
            from app.modules.platform.control_plane.services.access_config_service import (
                access_config_service,
            )

            controls = access_config_service.get_org_controls(org_id)
            ai_codes |= access_config_service.ai_feature_codes()
        except Exception:
            pass
        return {
            "plan_key": plan_key,
            "plan_features": plan_features,
            "overrides": overrides,
            "controls": controls,
            "ai_codes": ai_codes,
        }

    def _enabled_from_snapshot(self, feature_code: str, snap: dict[str, Any]) -> bool:
        try:
            from app.modules.platform.control_plane.services.access_config_service import (
                access_config_service,
            )

            if not access_config_service.feature_allowed_by_org_controls(
                "",
                feature_code,
                controls=snap["controls"],
                ai_codes=snap["ai_codes"],
            ):
                return False
        except Exception:
            pass

        overrides: dict[str, bool] = snap["overrides"]
        if feature_code in overrides:
            return bool(overrides[feature_code])
        return feature_code in snap["plan_features"]

    def features_map(self, org_id: str, codes: list[str] | None = None) -> dict[str, bool]:
        """Effective feature entitlements for an org with O(1) DB round-trips."""
        snap = self._snapshot(org_id)
        target = codes if codes is not None else self._catalog_codes()
        return {code: self._enabled_from_snapshot(code, snap) for code in target}

    def has_feature(self, org_id: str, feature_code: str) -> bool:
        snap = self._snapshot(org_id)
        return self._enabled_from_snapshot(feature_code, snap)

    def require_feature(self, org_id: str, feature_code: str) -> None:
        if not self.has_feature(org_id, feature_code):
            plan_key = subscription_service.get_plan_key(org_id)
            raise FeatureNotEntitled(feature_code, plan_key)

    def list_effective_features(self, org_id: str) -> list[dict]:
        codes = self._catalog_codes()
        enabled_map = self.features_map(org_id, codes)
        return [{"feature_code": code, "enabled": bool(enabled_map.get(code))} for code in codes]

    def set_override(
        self,
        org_id: str,
        feature_code: str,
        *,
        enabled: bool,
        expires_at=None,
        break_glass: bool = False,
    ) -> dict:
        if enabled:
            plan_key = subscription_service.get_plan_key(org_id)
            plan_features = plan_service.get_plan_features(plan_key)
            if feature_code not in plan_features and not break_glass:
                raise ValueError(
                    f"Feature '{feature_code}' is not on plan '{plan_key}'. "
                    "Set break_glass=true for audited special grants."
                )
        return billing_repository.upsert_org_entitlement(
            org_id,
            feature_code=feature_code,
            enabled=enabled,
            expires_at=expires_at,
        )

    def disable_ai_features(self, org_id: str) -> list[dict]:
        results = []
        for code in sorted(AI_FEATURE_CODES):
            results.append(self.set_override(org_id, code, enabled=False))
        return results


entitlement_service = EntitlementService()
