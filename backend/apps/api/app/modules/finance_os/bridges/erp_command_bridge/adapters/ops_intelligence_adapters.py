from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import (
    AssetIntelligencePort,
    InventoryIntelligencePort,
    ProcurementIntelligencePort,
)


class ProcurementIntelligenceAdapter:
    """Finance OS implementation of ERP ProcurementIntelligencePort."""

    def analyze_spend(self, org_id: str) -> dict:
        from app.modules.finance_os.domain_intelligence.procurement.spend_analyzer import analyze_spend

        return analyze_spend(org_id)

    def detect_anomalies(self, org_id: str) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.procurement.anomaly_detector import detect_anomalies

        return detect_anomalies(org_id)

    def recommend_vendors(self, org_id: str, *, item_hint: str = "", limit: int = 5) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.procurement.vendor_recommender import recommend_vendors

        return recommend_vendors(org_id, item_hint=item_hint, limit=limit)

    def answer_query(self, org_id: str, *, query: str) -> dict:
        from app.modules.finance_os.domain_intelligence.procurement.procurement_copilot import answer_query

        return answer_query(org_id, query=query)


class InventoryIntelligenceAdapter:
    """Finance OS implementation of ERP InventoryIntelligencePort."""

    def predict_demand(self, org_id: str, *, item_id: str, horizon_days: int = 30) -> dict:
        from app.modules.finance_os.domain_intelligence.inventory.demand_predictor import predict_demand

        return predict_demand(org_id, item_id=item_id, horizon_days=horizon_days)

    def classify_velocity(self, *, issue_count_30d: int, issue_count_90d: int) -> str:
        from app.modules.finance_os.domain_intelligence.inventory.stock_risk_detector import classify_velocity

        return classify_velocity(issue_count_30d=issue_count_30d, issue_count_90d=issue_count_90d)

    def detect_stock_risk(self, balances: list[dict], *, reorder_days: int = 14) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.inventory.stock_risk_detector import detect_stock_risk

        return detect_stock_risk(balances, reorder_days=reorder_days)

    def detect_dead_stock(self, movements: list[dict], *, as_of: str | None = None, days: int = 90) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.inventory.dead_stock_detector import detect_dead_stock

        return detect_dead_stock(movements, as_of=as_of, days=days)

    def analyze(self, org_id: str, *, query: str) -> dict:
        from app.modules.finance_os.domain_intelligence.inventory.inventory_analyzer import analyze

        return analyze(org_id, query=query)


class AssetIntelligenceAdapter:
    """Finance OS implementation of ERP AssetIntelligencePort."""

    def classify_asset(self, description: str) -> dict:
        from app.modules.finance_os.domain_intelligence.assets.asset_classifier import classify_asset

        return classify_asset(description)

    def recommend_useful_life(self, hints: dict | None) -> int:
        from app.modules.finance_os.domain_intelligence.assets.useful_life_recommender import recommend_useful_life

        return recommend_useful_life(hints)

    def suggest(self, description: str, amount: float) -> dict:
        from app.modules.finance_os.domain_intelligence.assets.asset_copilot import suggest

        return suggest(description, amount)

    def detect_anomalies(self, assets: list[dict]) -> list[dict]:
        from app.modules.finance_os.domain_intelligence.assets.anomaly_detector import detect_anomalies

        return detect_anomalies(assets)


_procurement: ProcurementIntelligencePort | None = None
_inventory: InventoryIntelligencePort | None = None
_asset: AssetIntelligencePort | None = None
