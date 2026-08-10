from __future__ import annotations

from typing import Any

from app.modules.platform.billing.constants import (
    FEATURE_CODES,
    PLAN_FEATURES,
    PLAN_INCLUDED_CREDITS,
    PLAN_LIMITS,
)
from app.modules.platform.billing.repositories.billing_repository import billing_repository


class PlanService:
    def list_plans(self) -> list[dict[str, Any]]:
        rows = billing_repository.list_plans()
        if rows:
            return [
                {
                    **row,
                    "monthly_ai_credits": row.get("included_ai_credits"),
                    "included_ai_credits": row.get("included_ai_credits"),
                }
                for row in rows
            ]
        return [
            {
                "plan_key": k,
                "name": k.replace("_", " ").title(),
                "tier": i + 1,
                "monthly_price_inr": 0,
                "included_ai_credits": PLAN_INCLUDED_CREDITS.get(k, 0),
                "monthly_ai_credits": PLAN_INCLUDED_CREDITS.get(k, 0),
                "status": "active",
            }
            for i, k in enumerate(PLAN_FEATURES.keys())
        ]

    def get_plan(self, plan_key: str) -> dict[str, Any] | None:
        row = billing_repository.get_plan(plan_key)
        if row:
            return {
                **row,
                "monthly_ai_credits": row.get("included_ai_credits"),
                "features": billing_repository.get_plan_features(plan_key),
                "limits": billing_repository.get_plan_limits(plan_key),
            }
        if plan_key in PLAN_FEATURES:
            return {
                "plan_key": plan_key,
                "name": plan_key.replace("_", " ").title(),
                "tier": 1,
                "monthly_price_inr": 0,
                "included_ai_credits": PLAN_INCLUDED_CREDITS.get(plan_key, 0),
                "monthly_ai_credits": PLAN_INCLUDED_CREDITS.get(plan_key, 0),
                "status": "active",
                "features": sorted(PLAN_FEATURES[plan_key]),
                "limits": PLAN_LIMITS.get(plan_key, {}),
            }
        return None

    def get_plan_features(self, plan_key: str) -> set[str]:
        db_features = billing_repository.get_plan_features(plan_key)
        if db_features:
            return set(db_features)
        return set(PLAN_FEATURES.get(plan_key, frozenset()))

    def get_plan_limit(self, plan_key: str, limit_code: str) -> int | None:
        limits = billing_repository.get_plan_limits(plan_key)
        if limits:
            return limits.get(limit_code)
        return PLAN_LIMITS.get(plan_key, {}).get(limit_code)

    def get_included_ai_credits(self, plan_key: str) -> float:
        row = billing_repository.get_plan(plan_key)
        if row and row.get("included_ai_credits") is not None:
            return float(row["included_ai_credits"])
        return float(PLAN_INCLUDED_CREDITS.get(plan_key, 0))

    def create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_key = str(payload["plan_key"]).strip()
        if not plan_key:
            raise ValueError("plan_key is required")
        if billing_repository.get_plan(plan_key):
            raise ValueError(f"plan already exists: {plan_key}")
        billing_repository.create_plan(
            plan_key=plan_key,
            name=str(payload.get("name") or plan_key),
            tier=int(payload.get("tier") or 1),
            monthly_price_inr=float(payload.get("monthly_price_inr") or 0),
            included_ai_credits=float(payload.get("included_ai_credits") or 0),
            status=str(payload.get("status") or "active"),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        )
        features = payload.get("features")
        if isinstance(features, list) and features:
            self.replace_features(plan_key, features)
        limits = payload.get("limits")
        if isinstance(limits, list) and limits:
            self.replace_limits(plan_key, limits)
        detail = self.get_plan(plan_key)
        assert detail is not None
        return detail

    def update_plan(self, plan_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        existing = billing_repository.get_plan(plan_key)
        if not existing and plan_key not in PLAN_FEATURES:
            raise LookupError(f"plan not found: {plan_key}")
        if not existing:
            billing_repository.create_plan(
                plan_key=plan_key,
                name=str(payload.get("name") or plan_key),
                tier=int(payload.get("tier") or 1),
                monthly_price_inr=float(payload.get("monthly_price_inr") or 0),
                included_ai_credits=float(
                    payload.get("included_ai_credits")
                    if payload.get("included_ai_credits") is not None
                    else PLAN_INCLUDED_CREDITS.get(plan_key, 0)
                ),
                status=str(payload.get("status") or "active"),
            )
        else:
            fields = {
                k: payload[k]
                for k in (
                    "name",
                    "tier",
                    "monthly_price_inr",
                    "included_ai_credits",
                    "status",
                    "metadata",
                )
                if k in payload
            }
            if fields:
                billing_repository.update_plan(plan_key, fields)
        return self.get_plan(plan_key) or {}

    def replace_features(self, plan_key: str, features: list[dict[str, Any] | str]) -> list[str]:
        normalized: list[dict[str, Any]] = []
        for item in features:
            if isinstance(item, str):
                normalized.append({"feature_code": item, "enabled": True})
            else:
                code = str(item.get("feature_code") or "")
                if code and code not in FEATURE_CODES:
                    # allow unknown codes once catalog grows
                    pass
                normalized.append(
                    {
                        "feature_code": code,
                        "enabled": bool(item.get("enabled", True)),
                    }
                )
        return billing_repository.replace_plan_features(plan_key, normalized)

    def replace_limits(self, plan_key: str, limits: list[dict[str, Any]]) -> dict[str, int | None]:
        return billing_repository.replace_plan_limits(plan_key, limits)

    def deprecate_plan(self, plan_key: str) -> dict[str, Any]:
        count = billing_repository.count_subscriptions_for_plan(plan_key)
        if not billing_repository.get_plan(plan_key) and plan_key not in PLAN_FEATURES:
            raise LookupError(f"plan not found: {plan_key}")
        return self.update_plan(plan_key, {"status": "deprecated", "subscriber_count": count})


plan_service = PlanService()
