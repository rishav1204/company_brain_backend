from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha1
from time import sleep

from app.core.config import settings
from app.modules.finance_os.agents.services import context_service
from app.modules.finance_os.platform_ai_runtime.context.context_cache import context_cache
from app.modules.finance_os.platform_ai_runtime.context.context_ranker import context_ranker
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import (
    ResolvedEntity,
    RetrievalPlan,
    RetrievalSource,
)
from app.modules.finance_os.platform_ai_runtime.engine.failure_taxonomy import FailureClass, classify_exception
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState
from app.modules.finance_os.platform_ai_runtime.services.executor import executor
from app.modules.finance_os.platform_ai_runtime.security.context_boundary import enforce_retrieval_params
from app.services.logger import log_event
from app.services.retrieval_service import retrieve_context


def _looks_uuid(value: str | None) -> bool:
    if not value:
        return False
    import re

    return bool(
        re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            str(value),
            re.I,
        )
    )


def _looks_entity_ref(value: str | None) -> bool:
    """True for UUIDs or document codes (INV-001) — not bare words like 'invoice'."""
    if not value:
        return False
    import re

    s = str(value).strip()
    if _looks_uuid(s):
        return True
    if re.match(r"^(inv|po|grn|ap|ar|je|jv)[-_][\w-]+$", s, re.I):
        return True
    # Reject type nouns accidentally bound as ids
    if s.lower() in {
        "invoice",
        "vendor",
        "customer",
        "journal",
        "po",
        "ap",
        "ar",
        "none",
        "null",
        "undefined",
    }:
        return False
    return len(s) >= 6


def _typed_id_fields(etype: str | None, eid: str | None) -> dict:
    """Map resolved entity type + id onto tool required param names."""
    if not etype or not eid:
        return {}
    t = etype.lower()
    mapping = {
        "invoice": "invoice_id",
        "ap_invoice": "invoice_id",
        "ar_invoice": "invoice_id",
        "sales_invoice": "invoice_id",
        "vendor": "vendor_id",
        "customer": "customer_id",
        "po": "po_id",
        "journal": "journal_id",
        "grn": "grn_id",
        "asset": "asset_id",
        "voucher": "voucher_id",
        "bank": "account_id",
        "item": "item_id",
        "account": "account_id",
        "claim": "claim_id",
        "return": "return_id",
    }
    key = mapping.get(t)
    return {key: eid} if key else {}


def _primary_entity(entities: list[ResolvedEntity]) -> tuple[str | None, str | None, str | None]:
    """Return (entity_type, entity_id, source). Prefer bound ids; fall back to document labels."""
    ranked = sorted(
        [e for e in entities if e.entity_id and not e.needs_clarification and _looks_entity_ref(e.entity_id)],
        key=lambda e: e.confidence,
        reverse=True,
    )
    if ranked:
        return ranked[0].entity_type, ranked[0].entity_id, ranked[0].source
    # Clarification / unbound: still allow document-code lookup via label (INV-001)
    for e in entities:
        label = (e.label or "").strip()
        if label and _looks_entity_ref(label) and e.entity_type in {
            "invoice",
            "ap_invoice",
            "ar_invoice",
            "sales_invoice",
            "po",
            "vendor",
            "customer",
        }:
            return e.entity_type, label, e.source
    if entities:
        eid = entities[0].entity_id
        if _looks_entity_ref(eid):
            return entities[0].entity_type, eid, entities[0].source
        return entities[0].entity_type, None, entities[0].source
    return None, None, None


def _build_payload(world_state: WorldState | None, entities: list[ResolvedEntity], query: str) -> dict:
    payload: dict = {"query": query}
    etype, eid, _src = _primary_entity(entities)
    if world_state and world_state.screen:
        if world_state.screen.entity_type:
            payload["entity_type"] = world_state.screen.entity_type
        if world_state.screen.entity_id:
            payload["entity_id"] = world_state.screen.entity_id
    if etype and not payload.get("entity_type"):
        payload["entity_type"] = etype
    if eid and not payload.get("entity_id"):
        payload["entity_id"] = eid
    # Typed IDs from resolved entity (critical for chat-only asks like INV-001)
    for k, v in _typed_id_fields(etype, eid).items():
        payload.setdefault(k, v)
    # Convenience ERP IDs from world state
    if world_state:
        if world_state.current_invoice_id:
            payload.setdefault("invoice_id", world_state.current_invoice_id)
        if world_state.current_vendor_id:
            payload.setdefault("vendor_id", world_state.current_vendor_id)
        if world_state.current_customer_id:
            payload.setdefault("customer_id", world_state.current_customer_id)
        if world_state.current_po_id:
            payload.setdefault("po_id", world_state.current_po_id)
        if world_state.current_journal_id:
            payload.setdefault("journal_id", world_state.current_journal_id)
        if world_state.screen and world_state.screen.entity_id and world_state.screen.entity_type:
            for k, v in _typed_id_fields(world_state.screen.entity_type, world_state.screen.entity_id).items():
                payload.setdefault(k, v)
    if world_state and world_state.org and world_state.org.fiscal_period_id:
        payload["period_id"] = world_state.org.fiscal_period_id
    if world_state and world_state.selection:
        payload.update({k: v for k, v in world_state.selection.items() if v})
    if world_state and world_state.filters:
        payload["filters"] = world_state.filters
    return payload


def _plan_sig(plan: RetrievalPlan) -> str:
    parts = [f"{s.source_type}:{s.tool}.{s.method}" for s in plan.sources]
    raw = "|".join(parts) + "|" + (plan.query or "")[:120]
    return sha1(raw.encode("utf-8")).hexdigest()[:24]


class RetrievalOrchestrator:
    """Parallel multi-source retrieval + cache + freshness stamps (Wave 4)."""

    def fetch(
        self,
        org_id: str,
        *,
        plan: RetrievalPlan,
        world_state: WorldState | None,
        entities: list[ResolvedEntity],
        user_id: str = "platform_context",
        roles: list[str] | None = None,
        goal_id: str | None = None,
        run_id: str | None = None,
        attrs: dict | None = None,
        use_cache: bool = True,
    ) -> dict:
        payload = enforce_retrieval_params(
            _build_payload(world_state, entities, plan.query),
            org_id=org_id,
            world_state=world_state,
            attrs=attrs,
        )
        etype, eid, esource = _primary_entity(entities)
        as_of = datetime.now(timezone.utc).isoformat()
        entity_key = f"{etype or ''}:{eid or (world_state.screen.entity_id if world_state and world_state.screen else '')}"
        sig = _plan_sig(plan)

        if use_cache:
            cached = context_cache.get(org_id, plan_sig=sig, entity_key=entity_key, query=plan.query)
            if cached:
                # Prefer fresher timestamps when present; surface as cache hit
                out = dict(cached)
                out["context_cache_hit"] = True
                out.setdefault("retrieval_trace", [])
                out["retrieval_trace"] = [
                    *list(out.get("retrieval_trace") or []),
                    {"source": "context_cache", "ok": True, "empty": False},
                ]
                return out

        memory: list[dict] = []
        graph: list[dict] = []
        erp_facts: dict = {}
        documents: list[dict] = []
        policies: list[dict] = []
        workflow_state: list[dict] = []
        approval_queue: list[dict] = []
        recent_events: list[dict] = []
        trace: list[dict] = []
        failures: list[dict] = []

        def _record_failure(source: RetrievalSource, exc: BaseException, attempt: int) -> None:
            classified = classify_exception(exc, context="retrieval")
            entry = {
                "source": source.source_type,
                "tool": source.tool,
                "method": source.method,
                "attempt": attempt,
                "failure": classified.to_dict(),
                "at": datetime.now(timezone.utc).isoformat(),
            }
            failures.append(entry)
            log_event(
                "m38.context.retrieval_failed",
                org_id=org_id,
                source=source.source_type,
                tool=source.tool,
                method=source.method,
                attempt=attempt,
                failure_class=classified.failure_class.value,
                detail=classified.message,
                goal_id=goal_id or "",
                run_id=run_id or "",
            )
            try:
                from app.services.repositories import audit_repo

                audit_repo.create_log(
                    org_id=org_id,
                    actor_type="agent",
                    actor_id="platform_context",
                    event_type="m38.retrieval.failed",
                    object_ref=f"goal:{goal_id or 'none'}",
                    payload_jsonb=entry,
                )
            except Exception as audit_exc:
                log_event("m38.context.retrieval_audit_failed", detail=str(audit_exc))

        def run_source_once(source: RetrievalSource) -> tuple[str, object]:
            # Platform: current UI context (world state snapshot — no external call)
            if source.source_type == "platform" and source.tool == "ui_context":
                ui = {
                    "screen": world_state.screen.model_dump() if world_state and world_state.screen else {},
                    "selection": (world_state.selection if world_state else {}) or {},
                    "filters": (world_state.filters if world_state else {}) or {},
                    "search": (world_state.search if world_state else {}) or {},
                    "sort": (world_state.sort if world_state else {}) or {},
                    "roles": (world_state.roles if world_state else []) or [],
                    "timestamp": as_of,
                    "source": "ui_context",
                }
                return "ui_context", ui

            if source.source_type == "platform" and source.tool == "approval_queue":
                from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

                items = goal_manager.list_approval_queue(org_id)
                payload_items = [i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in items]
                return "approval_queue", payload_items

            if source.source_type == "platform" and source.tool == "workflow_state":
                items: list[dict] = []
                if world_state and world_state.active_workflows:
                    items.extend(list(world_state.active_workflows))
                if world_state and world_state.pending_approvals:
                    items.extend(
                        [{**a, "channel": "pending_approval"} for a in world_state.pending_approvals if isinstance(a, dict)]
                    )
                # Optional journal approval queue for workflow screen
                try:
                    if source.method in {"active", "list"} and not items:
                        from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

                        items = [
                            i.model_dump() if hasattr(i, "model_dump") else dict(i)
                            for i in goal_manager.list_approval_queue(org_id)
                        ]
                except Exception:
                    pass
                return "workflow_state", items

            if source.source_type == "platform" and source.tool == "recent_events":
                # From world state navigation / recent entities only (no invent)
                ev: list[dict] = []
                if world_state:
                    for item in (world_state.recent_navigation or [])[-10:]:
                        if isinstance(item, dict):
                            ev.append({**item, "kind": "navigation"})
                    for item in (world_state.recently_viewed or [])[-10:]:
                        if isinstance(item, dict):
                            ev.append({**item, "kind": "viewed"})
                return "recent_events", ev

            if source.source_type == "memory" or (source.tool == "memory" and source.method == "search"):
                from app.modules.finance_os.agents.bridges import m27_bridge

                hits = m27_bridge.search(
                    org_id,
                    plan.query,
                    entity_type=etype,
                    entity_id=eid,
                    top_k=15,
                )
                return "memory", hits
            if source.source_type == "graph" or (source.tool == "graph" and source.method == "traverse"):
                from app.modules.finance_os.agents.bridges import m28_bridge

                target = eid or (world_state.screen.entity_id if world_state and world_state.screen else None)
                paths = m28_bridge.lineage(org_id, target) if target and _looks_entity_ref(str(target)) else []
                return "graph", paths if isinstance(paths, list) else ([paths] if paths else [])
            if source.source_type == "bridge" and source.tool == "agent":
                ctx = context_service.build(org_id, "platform_runtime", payload)
                return "agent_context", ctx
            if source.source_type == "bridge" and source.tool == "invoice":
                from app.modules.finance_os.agents.bridges import m25_bridge

                inv_id = payload.get("entity_id") or payload.get("invoice_id") or ""
                return "invoice", m25_bridge.invoice_context(org_id, str(inv_id))
            if source.source_type == "bridge" and source.tool == "gst":
                from app.modules.finance_os.agents.bridges import m21_bridge

                return "gst", m21_bridge.compliance_context(org_id, str(eid or ""))
            if source.source_type == "documents" or source.tool == "documents":
                contexts, citations = retrieve_context(org_id, plan.query, subject_ref=eid, top_k=8)
                docs = [
                    {"content": c, "citation": cit.model_dump() if hasattr(cit, "model_dump") else cit}
                    for c, cit in zip(contexts, citations)
                ]
                return "documents", docs
            if source.source_type == "erp" and source.tool and source.method:
                # Skip detail getters when required id is still missing after payload merge
                detail_required = {
                    ("ap", "get_invoice"): "invoice_id",
                    ("ap", "get_vendor"): "vendor_id",
                    ("ar", "get_invoice"): "invoice_id",
                    ("ar", "get_customer"): "customer_id",
                    ("journals", "get"): "journal_id",
                    ("procurement", "get_po"): "po_id",
                    ("vouchers", "get"): "voucher_id",
                    ("coa", "get_account"): "account_id",
                    ("banking", "get_account"): "account_id",
                }
                need = detail_required.get((source.tool, source.method))
                merged = {**source.params, **{k: v for k, v in payload.items() if k != "query"}}
                if need and not merged.get(need) and not merged.get("entity_id"):
                    return f"erp:{source.tool}.{source.method}", {
                        "status": "skipped",
                        "detail": f"missing_{need}",
                        "target": source.tool,
                    }
                result = executor.run(
                    org_id,
                    tool=source.tool,
                    method=source.method,
                    params={**source.params, "query": plan.query, **{k: v for k, v in payload.items() if k != "query"}},
                    actor_id=user_id,
                    roles=roles,
                    attrs=attrs,
                    human_approved=True,
                )
                return f"erp:{source.tool}.{source.method}", result
            return source.source_type, {}

        def run_source(source: RetrievalSource) -> tuple[str, object, bool]:
            max_retries = max(0, int(settings.m38_retrieval_max_retries))
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    key, data = run_source_once(source)
                    return key, data, True
                except Exception as exc:
                    last_exc = exc
                    _record_failure(source, exc, attempt + 1)
                    if attempt < max_retries:
                        delay = (settings.m38_retrieval_retry_base_ms * (2**attempt)) / 1000.0
                        sleep(min(delay, 2.0))
            try:
                if source.source_type == "memory":
                    return "memory", [], False
                if source.source_type == "graph":
                    return "graph", [], False
                if source.source_type == "documents":
                    return "documents", [], False
            except Exception as fallback_exc:
                _record_failure(source, fallback_exc, max_retries + 2)
            if last_exc:
                return source.source_type, {}, False
            return source.source_type, {}, False

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(run_source, s): s for s in plan.sources}
            for fut in as_completed(futures):
                source = futures[fut]
                try:
                    key, data, ok = fut.result()
                except Exception as exc:
                    _record_failure(source, exc, -1)
                    key, data, ok = source.source_type, {}, False
                trace.append(
                    {
                        "source": key,
                        "tool": source.tool,
                        "method": source.method,
                        "ok": ok and bool(data or ok),
                        "empty": not bool(data),
                        "cross_module": source.cross_module,
                        "as_of": as_of,
                    }
                )
                if key == "memory" and isinstance(data, list):
                    memory.extend(data)
                elif key == "graph" and isinstance(data, list):
                    graph.extend(data)
                elif key == "documents" and isinstance(data, list):
                    documents.extend(data)
                elif key == "approval_queue" and isinstance(data, list):
                    approval_queue.extend(data)
                elif key == "workflow_state" and isinstance(data, list):
                    workflow_state.extend(data)
                elif key == "recent_events" and isinstance(data, list):
                    recent_events.extend(data)
                elif key == "ui_context" and isinstance(data, dict):
                    erp_facts["ui_context"] = data
                elif key == "agent_context":
                    ctx = data
                    if hasattr(ctx, "memory_snippets"):
                        memory.extend(ctx.memory_snippets or [])
                    if hasattr(ctx, "graph_paths"):
                        graph.extend(ctx.graph_paths or [])
                    if hasattr(ctx, "erp_facts"):
                        erp_facts.update(ctx.erp_facts or {})
                    if hasattr(ctx, "policy_flags"):
                        policies.extend(ctx.policy_flags or [])
                elif key.startswith("erp:"):
                    # Never promote tool errors into usable ERP facts (they pollute answer fallbacks)
                    # Skipped (missing id) and missing-param errors are soft — not user-facing failures
                    if isinstance(data, dict) and data.get("status") == "skipped":
                        pass
                    elif isinstance(data, dict) and data.get("status") in {"error", "pending_approval"}:
                        detail = str(data.get("detail") or data.get("status") or "")
                        # Soft: missing params, and non-critical analytics KPI dumps
                        if "Missing required params" in detail:
                            pass
                        elif source.tool == "analytics" and detail in {
                            "tool_execution_failed",
                            "Invoice not found",
                        }:
                            log_event(
                                "m38.context.analytics_soft_miss",
                                org_id=org_id,
                                tool=source.tool,
                                method=source.method,
                                detail=detail,
                            )
                        else:
                            failures.append(
                                {
                                    "source": key,
                                    "tool": source.tool,
                                    "method": source.method,
                                    "attempt": 0,
                                    "failure": {
                                        "failure_class": "tool_error",
                                        "message": detail,
                                    },
                                    "at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                    else:
                        erp_facts[key] = data
                elif key in {"invoice", "gst"}:
                    if isinstance(data, dict) and data.get("status") in {"error", "skipped"}:
                        detail = str(data.get("detail") or data.get("status") or "")
                        if data.get("status") == "skipped" or "Missing required" in detail:
                            pass
                        else:
                            failures.append(
                                {
                                    "source": key,
                                    "tool": source.tool,
                                    "method": source.method,
                                    "attempt": 0,
                                    "failure": {
                                        "failure_class": "tool_error",
                                        "message": detail,
                                    },
                                    "at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                    else:
                        erp_facts[key] = data

        # Authoritative ERP snapshot for primary entity
        try:
            if etype and eid:
                tool_map = {
                    "invoice": ("ap", "get_invoice"),
                    "ap_invoice": ("ap", "get_invoice"),
                    "sales_invoice": ("ar", "get_invoice"),
                    "ar_invoice": ("ar", "get_invoice"),
                    "journal": ("journals", "get"),
                    "vendor": ("ap", "get_vendor"),
                    "customer": ("ar", "get_customer"),
                    "po": ("procurement", "get_po"),
                }
                # Prefer AR get when enrichment came from AR ledger
                if str(etype).lower() == "invoice" and (esource or "").startswith("erp_ar"):
                    t = ("ar", "get_invoice")
                else:
                    t = tool_map.get(str(etype).lower())
                if t:
                    tool, method = t
                    snap_params = {"entity_id": eid, **_typed_id_fields(etype, eid)}
                    primary = executor.run(
                        org_id,
                        tool=tool,
                        method=method,
                        params=snap_params,
                        actor_id=user_id,
                        roles=roles,
                        attrs=attrs,
                        human_approved=True,
                    )
                    # If AP miss for generic invoice, try AR once (and vice versa)
                    if isinstance(primary, dict) and primary.get("status") == "error":
                        alt = None
                        if tool == "ap" and str(etype).lower() in {"invoice", "ap_invoice"}:
                            alt = ("ar", "get_invoice")
                        elif tool == "ar" and str(etype).lower() in {"invoice", "ar_invoice", "sales_invoice"}:
                            alt = ("ap", "get_invoice")
                        if alt:
                            primary = executor.run(
                                org_id,
                                tool=alt[0],
                                method=alt[1],
                                params=snap_params,
                                actor_id=user_id,
                                roles=roles,
                                attrs=attrs,
                                human_approved=True,
                            )
                            if isinstance(primary, dict) and primary.get("status") != "error":
                                tool, method = alt
                    if isinstance(primary, dict) and primary.get("status") in {"error", "pending_approval"}:
                        # Soft-miss after ledger fallback: log only — do not mark retrieval failed
                        # (list tools / other facts can still answer; "not found" is data, not a tool crash)
                        detail = str(primary.get("detail") or primary.get("status"))
                        log_event(
                            "m38.context.primary_snapshot_miss",
                            org_id=org_id,
                            tool=tool,
                            method=method,
                            detail=detail,
                            entity_type=str(etype or ""),
                            entity_id=str(eid or "")[:64],
                        )
                    elif isinstance(primary, dict) and primary.get("status") != "skipped":
                        erp_facts["primary_entity_snapshot"] = primary
        except Exception as exc:
            classified = classify_exception(exc, context="retrieval")
            failures.append({"source": "primary_entity_snapshot", "failure": classified.to_dict()})
            log_event(
                "m38.context.retrieval_failed",
                org_id=org_id,
                source="primary_entity_snapshot",
                detail=str(exc),
                failure_class=FailureClass.RETRIEVAL.value,
            )

        complete = len(failures) == 0
        if plan.sources and not (
            memory or graph or erp_facts or documents or approval_queue or workflow_state
        ):
            complete = False

        result = {
            "memory": memory,
            "graph": graph,
            "erp_facts": erp_facts,
            "documents": documents,
            "policies": policies,
            "workflow_state": workflow_state,
            "approval_queue": approval_queue,
            "recent_events": recent_events,
            "retrieval_trace": [{"as_of": as_of, **t} for t in trace],
            "retrieval_failures": failures,
            "retrieval_complete": complete,
            "context_cache_hit": False,
            "planner_hints": {
                "partial_context": not complete,
                "failed_sources": [f.get("source") for f in failures],
                "action": "continue_with_partial_context" if failures else "ok",
            },
        }
        result["item_meta"] = [
            m.model_dump() for m in context_ranker.build_item_meta(result, as_of=as_of)
        ]

        log_event(
            "m38.context.retrieval_complete",
            org_id=org_id,
            source_count=len(plan.sources),
            failure_count=len(failures),
            complete=complete,
            goal_id=goal_id or "",
        )

        if use_cache and complete:
            context_cache.set(
                org_id,
                plan_sig=sig,
                entity_key=entity_key,
                query=plan.query,
                payload=result,
            )

        return result


retrieval_orchestrator = RetrievalOrchestrator()
