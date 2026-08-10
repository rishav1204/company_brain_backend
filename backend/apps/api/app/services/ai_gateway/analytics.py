"""AI usage analytics — aggregate telemetry (Wave 6)."""

from __future__ import annotations

from typing import Any

from app.services.cache.redis_cache import get_cached, set_cached
from app.services.logger import log_event

NS = "ai.gateway.analytics"


class AIUsageAnalytics:
    """In-memory/Redis counters + optional SQL rollups from billing.ai_usage."""

    def record(
        self,
        org_id: str,
        *,
        model: str,
        execution_class: str,
        tokens: int,
        cost_usd: float,
        latency_ms: float,
        cache_hit: bool,
        failed: bool = False,
        saved_cost_usd: float = 0.0,
    ) -> None:
        day_key = {"d": "totals"}
        cur = get_cached(org_id, NS, day_key) or {
            "requests": 0,
            "failures": 0,
            "tokens": 0,
            "cost_usd": 0.0,
            "latency_ms_sum": 0.0,
            "cache_hits": 0,
            "cache_lookups": 0,
            "savings_usd": 0.0,
            "by_model": {},
            "by_class": {},
        }
        cur["requests"] = int(cur.get("requests", 0)) + 1
        if failed:
            cur["failures"] = int(cur.get("failures", 0)) + 1
        cur["tokens"] = int(cur.get("tokens", 0)) + int(tokens)
        cur["cost_usd"] = float(cur.get("cost_usd", 0)) + float(cost_usd)
        cur["latency_ms_sum"] = float(cur.get("latency_ms_sum", 0)) + float(latency_ms)
        cur["cache_lookups"] = int(cur.get("cache_lookups", 0)) + 1
        if cache_hit:
            cur["cache_hits"] = int(cur.get("cache_hits", 0)) + 1
        cur["savings_usd"] = float(cur.get("savings_usd", 0)) + float(saved_cost_usd)
        bm = cur.get("by_model") if isinstance(cur.get("by_model"), dict) else {}
        bm[model] = int(bm.get(model, 0)) + 1
        cur["by_model"] = bm
        bc = cur.get("by_class") if isinstance(cur.get("by_class"), dict) else {}
        bc[execution_class] = int(bc.get(execution_class, 0)) + 1
        cur["by_class"] = bc
        set_cached(org_id, NS, cur, day_key, ttl=86400)
        log_event(
            "ai.analytics.sample",
            org_id=org_id,
            requests=cur["requests"],
            cost_usd=cur["cost_usd"],
            cache_hit_rate=self._hit_rate(cur),
        )

    def snapshot(self, org_id: str) -> dict[str, Any]:
        cur = get_cached(org_id, NS, {"d": "totals"}) or {}
        req = int(cur.get("requests", 0)) or 1
        return {
            "requests": int(cur.get("requests", 0)),
            "failures": int(cur.get("failures", 0)),
            "tokens": int(cur.get("tokens", 0)),
            "cost_usd": float(cur.get("cost_usd", 0)),
            "avg_latency_ms": round(float(cur.get("latency_ms_sum", 0)) / req, 2),
            "cache_hit_rate": self._hit_rate(cur),
            "savings_usd": float(cur.get("savings_usd", 0)),
            "by_model": cur.get("by_model") or {},
            "by_class": cur.get("by_class") or {},
            "failure_rate": round(int(cur.get("failures", 0)) / req, 4),
        }

    def _hit_rate(self, cur: dict) -> float:
        lookups = int(cur.get("cache_lookups", 0)) or 0
        if not lookups:
            return 0.0
        return round(int(cur.get("cache_hits", 0)) / lookups, 4)

    def from_database(self, org_id: str, *, limit: int = 100) -> list[dict]:
        try:
            from app.services.db import get_db_conn, set_rls_org

            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT provider, model, operation_code, prompt_tokens, completion_tokens,
                               total_tokens, cost_usd, credits_charged, created_at::text
                        FROM billing.ai_usage
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception:
            return []


ai_usage_analytics = AIUsageAnalytics()
