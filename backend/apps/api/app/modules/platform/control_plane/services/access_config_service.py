"""Resolve effective feature/screen/controls for a principal."""

from __future__ import annotations

from typing import Any, Collection

from app.modules.platform.billing.constants import FEATURE_CODES
from app.modules.platform.billing.services.entitlement_service import (
    AI_FEATURE_CODES,
    entitlement_service,
)
from app.modules.platform.control_plane.repositories.control_plane_repository import (
    control_plane_repository,
)


class AccessConfigService:
    _ai_codes_cache: frozenset[str] | None = None

    def get_org_controls(self, org_id: str) -> dict[str, Any]:
        row = control_plane_repository.get_org_controls(org_id)
        if row:
            return self._normalize_org_controls(row)
        return {
            "org_id": org_id,
            "lifecycle_status": "active",
            "login_allowed": True,
            "ai_enabled": True,
            "erp_modules_enabled": True,
            "api_access_allowed": True,
            "support_priority": "standard",
            "denied_screen_keys": [],
            "metadata": {},
        }

    def _normalize_org_controls(self, row: dict[str, Any]) -> dict[str, Any]:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        denied_screens = row.get("denied_screen_keys")
        if denied_screens is None:
            denied_screens = meta.get("denied_screen_keys") or []
        if not isinstance(denied_screens, list):
            denied_screens = list(denied_screens) if denied_screens else []
        return {
            **row,
            "metadata": meta,
            "denied_screen_keys": [str(s) for s in denied_screens if s],
        }

    def ai_feature_codes(self) -> frozenset[str]:
        if AccessConfigService._ai_codes_cache is not None:
            return AccessConfigService._ai_codes_cache
        codes = set(AI_FEATURE_CODES)
        try:
            for row in control_plane_repository.list_features():
                if row.get("is_ai"):
                    codes.add(str(row.get("feature_code") or ""))
        except Exception:
            pass
        codes.discard("")
        AccessConfigService._ai_codes_cache = frozenset(codes)
        return AccessConfigService._ai_codes_cache

    def feature_allowed_by_org_controls(
        self,
        org_id: str,
        feature_code: str,
        *,
        controls: dict[str, Any] | None = None,
        ai_codes: Collection[str] | None = None,
    ) -> bool:
        ctl = controls if controls is not None else self.get_org_controls(org_id)
        if str(ctl.get("lifecycle_status") or "active") in {"frozen", "suspended", "offboarding"}:
            if not ctl.get("api_access_allowed", True):
                return False
        is_ai = feature_code in (ai_codes if ai_codes is not None else self.ai_feature_codes())
        if is_ai and not bool(ctl.get("ai_enabled", True)):
            return False
        if not is_ai and not bool(ctl.get("erp_modules_enabled", True)):
            if feature_code in {"api_platform"}:
                return True
            return False
        return True

    def feature_allowed_for_user(self, org_id: str, user_id: str | None, feature_code: str) -> bool:
        if not user_id:
            return True
        uc = control_plane_repository.get_user_controls(org_id, user_id)
        if not uc:
            return True
        denied = uc.get("denied_feature_codes") or []
        return feature_code not in denied

    def screen_allowed(
        self,
        org_id: str,
        user_id: str | None,
        screen: dict[str, Any],
        *,
        controls: dict[str, Any] | None = None,
        features_enabled: dict[str, bool] | None = None,
        user_controls: dict[str, Any] | None = None,
        ai_codes: Collection[str] | None = None,
    ) -> bool:
        screen_key = screen.get("screen_key")
        ctl = controls if controls is not None else self.get_org_controls(org_id)
        if screen_key and screen_key in (ctl.get("denied_screen_keys") or []):
            return False
        uc = user_controls
        if uc is None and user_id:
            uc = control_plane_repository.get_user_controls(org_id, user_id)
        if uc and screen_key in (uc.get("denied_screen_keys") or []):
            return False
        feature_code = screen.get("feature_code")
        if feature_code:
            if not self.feature_allowed_by_org_controls(
                org_id, feature_code, controls=ctl, ai_codes=ai_codes
            ):
                return False
            if features_enabled is not None:
                if not features_enabled.get(feature_code, False):
                    return False
            elif not entitlement_service.has_feature(org_id, feature_code):
                return False
        return True

    def effective_boot(self, org_id: str, user_id: str, *, permissions: list[str] | None = None) -> dict[str, Any]:
        controls = self.get_org_controls(org_id)
        ai_codes = self.ai_feature_codes()
        features = entitlement_service.list_effective_features(org_id)
        user_controls = control_plane_repository.get_user_controls(org_id, user_id) or {
            "denied_feature_codes": [],
            "denied_screen_keys": [],
            "force_read_only": False,
        }
        denied_features = set(user_controls.get("denied_feature_codes") or [])
        filtered_features = []
        features_enabled: dict[str, bool] = {}
        for f in features:
            code = f["feature_code"]
            enabled = bool(f.get("enabled")) and code not in denied_features
            features_enabled[code] = enabled
            filtered_features.append({**f, "enabled": enabled})

        screens = []
        for screen in control_plane_repository.list_screens():
            # ERP /me/boot only needs tenant (ERP) screens. Platform-owner console
            # routes live under /platform/* and must not pollute product shell boot.
            console = str(screen.get("console") or "erp").lower()
            route = str(screen.get("route_path") or "")
            if console == "platform" or route == "/platform" or route.startswith("/platform/"):
                continue
            allowed = self.screen_allowed(
                org_id,
                user_id,
                screen,
                controls=controls,
                features_enabled=features_enabled,
                user_controls=user_controls,
                ai_codes=ai_codes,
            )
            screens.append({**screen, "allowed": allowed})

        return {
            "org_id": org_id,
            "user_id": user_id,
            "org_controls": controls,
            "features": filtered_features,
            "screens": screens,
            "user_controls": user_controls,
            "permissions": permissions or [],
        }

    def access_matrix(self, org_id: str) -> dict[str, Any]:
        """Platform UI: features + screens with sources for org-level restriction.

        Prefetch all inputs once; never call has_feature / get_org_controls per row
        (that path reopened DB connections and previously took 30s+).
        """
        from app.modules.platform.billing.repositories.billing_repository import billing_repository
        from app.modules.platform.billing.services.plan_service import plan_service
        from app.modules.platform.billing.services.subscription_service import subscription_service

        controls = self.get_org_controls(org_id)
        ai_codes = self.ai_feature_codes()
        plan_key = subscription_service.get_plan_key(org_id)
        plan_features = set(plan_service.get_plan_features(plan_key))
        overrides = {
            str(o["feature_code"]): bool(o.get("enabled"))
            for o in billing_repository.list_org_entitlement_overrides(org_id)
        }
        catalog = self.list_feature_catalog()

        features_out: list[dict[str, Any]] = []
        features_enabled: dict[str, bool] = {}
        for item in catalog:
            code = str(item.get("feature_code") or "")
            if not code:
                continue
            if item.get("status") and item.get("status") != "active":
                continue
            on_plan = code in plan_features
            has_ov = code in overrides
            master_ok = self.feature_allowed_by_org_controls(
                org_id, code, controls=controls, ai_codes=ai_codes
            )
            if not master_ok:
                effective = False
                source = "org_master_off"
            elif has_ov:
                effective = bool(overrides[code])
                source = "override_enabled" if effective else "override_disabled"
            elif on_plan:
                effective = True
                source = "plan"
            else:
                effective = False
                source = "not_on_plan"
            features_enabled[code] = effective
            features_out.append(
                {
                    "feature_code": code,
                    "name": item.get("name") or code,
                    "category": item.get("category"),
                    "is_ai": bool(item.get("is_ai")),
                    "on_plan": on_plan,
                    "override": overrides.get(code),
                    "enabled": effective,
                    "source": source,
                }
            )

        denied = set(controls.get("denied_screen_keys") or [])
        screens_out: list[dict[str, Any]] = []
        for screen in control_plane_repository.list_screens():
            key = str(screen.get("screen_key") or "")
            allowed = self.screen_allowed(
                org_id,
                None,
                screen,
                controls=controls,
                features_enabled=features_enabled,
                user_controls=None,
                ai_codes=ai_codes,
            )
            screens_out.append(
                {
                    **screen,
                    "denied": key in denied,
                    "allowed": allowed,
                }
            )

        return {
            "org_id": org_id,
            "plan_key": plan_key,
            "org_controls": controls,
            "features": features_out,
            "screens": screens_out,
        }

    def set_org_feature(
        self,
        org_id: str,
        feature_code: str,
        *,
        enabled: bool,
        break_glass: bool = False,
    ) -> dict[str, Any]:
        row = entitlement_service.set_override(
            org_id, feature_code, enabled=enabled, break_glass=break_glass
        )
        return {
            "feature_code": feature_code,
            "enabled": bool(row.get("enabled", enabled)),
            "override": row,
            "effective": entitlement_service.has_feature(org_id, feature_code),
        }

    def set_org_denied_screens(self, org_id: str, denied_screen_keys: list[str], *, actor_id: str | None) -> dict[str, Any]:
        existing = self.get_org_controls(org_id)
        meta = dict(existing.get("metadata") or {}) if isinstance(existing.get("metadata"), dict) else {}
        clean = sorted({str(k).strip() for k in denied_screen_keys if str(k).strip()})
        meta["denied_screen_keys"] = clean
        return self.patch_org_controls(org_id, {"metadata": meta}, actor_id=actor_id)

    def patch_org_controls(self, org_id: str, fields: dict[str, Any], *, actor_id: str | None) -> dict[str, Any]:
        # Allow top-level denied_screen_keys → metadata
        denied = fields.pop("denied_screen_keys", None)
        if denied is not None:
            existing = self.get_org_controls(org_id)
            meta = dict(fields.get("metadata") or existing.get("metadata") or {})
            if not isinstance(meta, dict):
                meta = {}
            meta["denied_screen_keys"] = sorted({str(k).strip() for k in denied if str(k).strip()})
            fields["metadata"] = meta
        control_plane_repository.upsert_org_controls(org_id, fields, actor_id=actor_id)
        return self._normalize_org_controls(self.get_org_controls(org_id) or {})

    def patch_user_controls(
        self, org_id: str, user_id: str, fields: dict[str, Any], *, actor_id: str | None
    ) -> dict[str, Any]:
        return control_plane_repository.upsert_user_controls(org_id, user_id, fields, actor_id=actor_id)

    def list_feature_catalog(self) -> list[dict[str, Any]]:
        rows = control_plane_repository.list_features()
        if rows:
            return rows
        return [
            {"feature_code": c, "name": c, "category": "erp", "is_ai": False, "status": "active"}
            for c in FEATURE_CODES
        ]


access_config_service = AccessConfigService()
