from __future__ import annotations

from app.modules.erp.consolidation.engine import ownership_engine


class OwnershipService:
    def compute_split(self, *, subsidiary_profit: float, ownership_percent: float) -> dict[str, float]:
        return ownership_engine.compute_ownership_split(
            subsidiary_profit=subsidiary_profit,
            ownership_percent=ownership_percent,
        )


ownership_service = OwnershipService()
