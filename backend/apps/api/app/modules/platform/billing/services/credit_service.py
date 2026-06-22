from __future__ import annotations

from typing import Any

from app.modules.platform.billing.constants import CREDIT_CATALOG, PLAN_INCLUDED_CREDITS
from app.modules.platform.billing.exceptions import InsufficientCredits
from app.modules.platform.billing.repositories.billing_repository import billing_repository
from app.modules.platform.billing.services.subscription_service import subscription_service


class CreditService:
    _reservations: dict[str, float] = {}

    def operation_cost(self, operation_code: str) -> float:
        return float(CREDIT_CATALOG.get(operation_code, CREDIT_CATALOG["generic_llm"]))

    def ensure_wallet(self, org_id: str, *, included_monthly: float | None = None) -> dict[str, Any]:
        if not billing_repository.schema_ready():
            return {"balance": included_monthly or 0}
        plan_key = subscription_service.get_plan_key(org_id)
        included = included_monthly if included_monthly is not None else PLAN_INCLUDED_CREDITS.get(plan_key, 0)
        return billing_repository.ensure_credit_wallet(org_id, included_monthly=float(included))

    def get_balance(self, org_id: str) -> float:
        if not billing_repository.schema_ready():
            return float(PLAN_INCLUDED_CREDITS.get(subscription_service.get_plan_key(org_id), 0))
        wallet = billing_repository.get_credit_wallet(org_id)
        if not wallet:
            wallet = self.ensure_wallet(org_id)
        return float(wallet.get("balance", 0))

    def reserve_credits(self, org_id: str, operation_code: str, *, amount: float | None = None) -> float:
        cost = amount if amount is not None else self.operation_cost(operation_code)
        if cost <= 0:
            return 0.0
        balance = self.get_balance(org_id)
        if balance < cost:
            raise InsufficientCredits(cost, balance)
        key = f"{org_id}:{operation_code}"
        self._reservations[key] = self._reservations.get(key, 0) + cost
        return cost

    def commit_deduction(
        self,
        org_id: str,
        operation_code: str,
        *,
        amount: float | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        cost = amount if amount is not None else self.operation_cost(operation_code)
        if cost <= 0:
            return {"balance_after": self.get_balance(org_id)}
        if not billing_repository.schema_ready():
            return {"balance_after": 0}
        key = f"{org_id}:{operation_code}"
        if key in self._reservations:
            self._reservations[key] = max(0, self._reservations[key] - cost)
        return billing_repository.adjust_credits(
            org_id,
            delta=-cost,
            reason="ai_operation",
            operation_code=operation_code,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )

    def grant_credits(self, org_id: str, amount: float, *, reason: str = "admin_grant") -> dict[str, Any]:
        self.ensure_wallet(org_id)
        return billing_repository.adjust_credits(org_id, delta=amount, reason=reason)

    def log_ai_usage(
        self,
        org_id: str,
        *,
        provider: str,
        model: str,
        operation_code: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float = 0,
        credits_charged: float = 0,
        **kwargs,
    ) -> dict[str, Any] | None:
        if not billing_repository.schema_ready():
            return None
        return billing_repository.record_ai_usage(
            org_id,
            provider=provider,
            model=model,
            operation_code=operation_code,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            credits_charged=credits_charged,
            reference_type=kwargs.get("reference_type"),
            reference_id=kwargs.get("reference_id"),
            metadata=kwargs.get("metadata"),
        )


credit_service = CreditService()
