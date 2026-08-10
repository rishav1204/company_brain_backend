from __future__ import annotations

from datetime import datetime, timezone

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ContextItemMeta,
    IntentResult,
    ResolvedEntity,
)
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState


def _screen_entity_id(world_state: WorldState | None) -> str | None:
    if world_state and world_state.screen:
        return world_state.screen.entity_id
    return None


def _screen_module(world_state: WorldState | None) -> str | None:
    if world_state and world_state.screen:
        return (world_state.screen.module or "").lower() or None
    return None


def _parse_ts(item: dict) -> float | None:
    for key in ("updated_at", "created_at", "timestamp", "as_of", "at"):
        raw = item.get(key)
        if not raw:
            continue
        try:
            if isinstance(raw, (int, float)):
                return float(raw)
            s = str(raw).replace("Z", "+00:00")
            return datetime.fromisoformat(s).timestamp()
        except Exception:
            continue
    return None


def _recency_boost(item: dict, now: float) -> float:
    ts = _parse_ts(item)
    if ts is None:
        return 0.0
    age = max(0.0, now - ts)
    # 0–0.25 within 7 days
    if age < 3600:
        return 0.25
    if age < 86400:
        return 0.18
    if age < 7 * 86400:
        return 0.10
    return 0.02


class ContextRanker:
    """Multi-signal ranking — only highest relevance proceeds (Wave 4)."""

    def score_item(
        self,
        item: dict,
        *,
        query: str,
        world_state: WorldState | None = None,
        entities: list[ResolvedEntity] | None = None,
        intent: IntentResult | None = None,
        now: float | None = None,
    ) -> float:
        base = float(item.get("final_score") or item.get("importance_score") or item.get("score") or 0.5)
        screen_id = _screen_entity_id(world_state)
        entity_ids = {e.entity_id for e in (entities or []) if e.entity_id}
        entity_types = {e.entity_type for e in (entities or []) if e.entity_type}
        now_ts = now or datetime.now(timezone.utc).timestamp()

        # Current screen / entity
        if screen_id and str(item.get("entity_id") or item.get("id") or "") == screen_id:
            base += 0.35
        if entity_ids and str(item.get("entity_id") or "") in entity_ids:
            base += 0.25
        if entity_types and str(item.get("entity_type") or item.get("type") or "") in entity_types:
            base += 0.1

        # Module match
        mod = _screen_module(world_state)
        text_blob = " ".join(
            str(item.get(k) or "") for k in ("content", "title", "module", "source", "status", "tool")
        ).lower()
        if mod:
            for token in ("ap", "ar", "gst", "treasury", "procurement", "journal", "invoice", "vendor"):
                if token in mod and token in text_blob:
                    base += 0.08
                    break

        # Workflow / approval priority
        status = str(item.get("status") or item.get("approval_status") or "").lower()
        if status in {"pending", "pending_approval", "blocked", "escalated"}:
            base += 0.2
        if item.get("approval_required") or item.get("blocked"):
            base += 0.15
        if world_state and world_state.pending_approvals:
            for pa in world_state.pending_approvals:
                if isinstance(pa, dict) and str(pa.get("id") or pa.get("entity_id") or "") and str(
                    pa.get("id") or pa.get("entity_id")
                ) in str(item):
                    base += 0.12

        # Conversation / query tokens
        q = (query or "").lower()
        for token in q.split()[:8]:
            if len(token) > 3 and token in text_blob:
                base += 0.04

        # Intent-specific
        if intent and intent.intent == "analysis" and item.get("amount") is not None:
            base += 0.05
        if intent and intent.intent == "workflow" and (
            "workflow" in text_blob or "approval" in text_blob
        ):
            base += 0.12

        # Recency
        base += _recency_boost(item, now_ts)

        # Business priority markers
        if item.get("risk") in {"high", "critical"} or item.get("exception"):
            base += 0.15
        if item.get("overdue") or item.get("exception_type"):
            base += 0.1

        # Cross-module relationship hop preference (lower hops better)
        hops = item.get("path_length") or item.get("hops")
        if hops is not None:
            try:
                base += max(0.0, 0.12 - 0.03 * int(hops))
            except Exception:
                pass

        return base

    def rank_memory(
        self,
        items: list[dict],
        *,
        query: str,
        world_state: WorldState | None = None,
        entities: list[ResolvedEntity] | None = None,
        intent: IntentResult | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        if not items:
            return []
        now = datetime.now(timezone.utc).timestamp()

        def scored(item: dict) -> float:
            return self.score_item(
                item, query=query, world_state=world_state, entities=entities, intent=intent, now=now
            )

        ranked = sorted(items, key=scored, reverse=True)
        return self._dedupe(ranked)[:top_k]

    def rank_documents(
        self,
        items: list[dict],
        *,
        query: str = "",
        world_state: WorldState | None = None,
        entities: list[ResolvedEntity] | None = None,
        intent: IntentResult | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        if not items:
            return []
        now = datetime.now(timezone.utc).timestamp()
        ranked = sorted(
            items,
            key=lambda i: self.score_item(
                i if isinstance(i, dict) else {"content": str(i)},
                query=query,
                world_state=world_state,
                entities=entities,
                intent=intent,
                now=now,
            ),
            reverse=True,
        )
        return self._dedupe(ranked)[:top_k]

    def rank_graph(
        self,
        items: list[dict],
        *,
        query: str = "",
        world_state: WorldState | None = None,
        entities: list[ResolvedEntity] | None = None,
        intent: IntentResult | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        if not items:
            return []
        now = datetime.now(timezone.utc).timestamp()
        ranked = sorted(
            items,
            key=lambda i: self.score_item(
                i if isinstance(i, dict) else {"content": str(i)},
                query=query,
                world_state=world_state,
                entities=entities,
                intent=intent,
                now=now,
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def rank_approvals(
        self,
        items: list[dict],
        *,
        world_state: WorldState | None = None,
        top_k: int = 8,
    ) -> list[dict]:
        if not items:
            return []
        screen_id = _screen_entity_id(world_state)

        def score(item: dict) -> float:
            s = 0.5
            if screen_id and screen_id in str(item):
                s += 0.4
            st = str(item.get("status") or "").lower()
            if st in {"pending", "pending_approval", "blocked"}:
                s += 0.3
            if str(item.get("risk_level") or "").lower() in {"high", "critical"}:
                s += 0.2
            return s

        return sorted(items, key=score, reverse=True)[:top_k]

    def build_item_meta(self, raw: dict, *, as_of: str | None = None) -> list[ContextItemMeta]:
        """Stamp provenance/freshness on retrieval buckets."""
        meta: list[ContextItemMeta] = []
        now = datetime.now(timezone.utc)
        as_of = as_of or now.isoformat()

        def _fresh_for(item: dict) -> tuple[float, float | None]:
            ts = _parse_ts(item)
            if ts is None:
                return 0.85, None
            age = max(0.0, now.timestamp() - ts)
            if age < 300:
                return 1.0, age
            if age < 3600:
                return 0.9, age
            if age < 86400:
                return 0.7, age
            if age < 7 * 86400:
                return 0.45, age
            return 0.2, age

        for key, bucket in (raw or {}).items():
            if key in {"retrieval_trace", "retrieval_failures", "retrieval_complete", "planner_hints", "item_meta"}:
                continue
            if isinstance(bucket, list):
                for item in bucket[:12]:
                    if not isinstance(item, dict):
                        meta.append(
                            ContextItemMeta(source=str(key), timestamp=as_of, confidence=0.5, freshness=0.85)
                        )
                        continue
                    fresh, stale = _fresh_for(item)
                    meta.append(
                        ContextItemMeta(
                            source=str(key),
                            timestamp=str(item.get("updated_at") or item.get("timestamp") or as_of),
                            version=str(item.get("version") or item.get("etag") or "") or None,
                            confidence=float(item.get("confidence") or item.get("score") or 0.5),
                            freshness=fresh,
                            staleness_seconds=stale,
                        )
                    )
            elif isinstance(bucket, dict) and bucket:
                fresh, stale = _fresh_for(bucket)
                meta.append(
                    ContextItemMeta(
                        source=str(key),
                        timestamp=str(bucket.get("updated_at") or as_of),
                        version=str(bucket.get("version") or "") or None,
                        confidence=0.7,
                        freshness=fresh,
                        staleness_seconds=stale,
                    )
                )
        return meta

    def _dedupe(self, ranked: list[dict]) -> list[dict]:
        deduped: dict[str, dict] = {}
        for item in ranked:
            if not isinstance(item, dict):
                key = str(item)[:60]
                if key not in deduped:
                    deduped[key] = {"content": str(item)}
                continue
            key = str(item.get("id") or item.get("entity_id") or item.get("content", "")[:60])
            if key not in deduped:
                deduped[key] = item
        return list(deduped.values())


context_ranker = ContextRanker()
