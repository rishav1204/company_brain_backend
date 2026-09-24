from __future__ import annotations

import time

from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.engine.goal_planner import goal_planner
from app.modules.finance_os.platform_ai_runtime.engine.observer import observer
from app.modules.finance_os.platform_ai_runtime.engine.rollback_manager import rollback_manager
from app.modules.finance_os.platform_ai_runtime.engine.compensation_engine import compensation_engine
from app.modules.finance_os.platform_ai_runtime.engine.failure_taxonomy import (
    FailureClass,
    classify_exception,
    classify_tool_result,
)
from app.modules.finance_os.platform_ai_runtime.engine.self_correction import self_correction
from app.modules.finance_os.platform_ai_runtime.context.platform_context_engine import platform_context_engine
from app.modules.finance_os.platform_ai_runtime.context.answer_synthesizer import answer_synthesizer
from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext
from app.modules.finance_os.platform_ai_runtime.context.world_state_builder import build_world_state, enrich_world_state_from_context, refresh_after_step
from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    CopilotChatResponse,
    GraphNodeSpec,
    ObservationResult,
    PlanMetadata,
    WorldState,
)
from app.modules.finance_os.platform_ai_runtime.services.executor import executor
from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry
from app.modules.finance_os.platform_ai_runtime.security.abuse_guard import AIBudgetExceeded, ai_abuse_guard
from app.modules.finance_os.platform_ai_runtime.security.ai_firewall import AIFirewallError, ai_firewall
from app.modules.platform.billing.billing_hooks import billing_ai_operation
from app.services.logger import log_event
from app.services.otel import otel_span
from app.services.repositories import audit_repo


def _max_steps() -> int:
    return max(1, int(getattr(settings, "m38_max_runtime_steps", 50) or 50))


def _max_node_retries() -> int:
    return max(0, int(getattr(settings, "m38_step_max_auto_retries", 2) or 2))


def _graph_progress(graph: ExecutionGraph) -> float:
    if not graph.nodes:
        return 0.0
    done = sum(1 for n in graph.nodes.values() if n.status in {"completed", "skipped"})
    return round(100.0 * done / len(graph.nodes), 1)


def _pending_approval_nodes(graph: ExecutionGraph) -> list[str]:
    return [n.id for n in graph.pending_approval_nodes()]


def _recover_interrupted_nodes(graph: ExecutionGraph) -> int:
    """After process restart, re-queue nodes stuck in 'running' (AI-07)."""
    recovered = 0
    for node in graph.nodes.values():
        if node.status == "running":
            node.status = "pending"
            recovered += 1
    return recovered


class RuntimeService:
    def schema_ready(self) -> bool:
        return goal_repository.schema_ready()

    def chat(
        self,
        org_id: str,
        *,
        message: str,
        user_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
        world_state: WorldState | None = None,
        goal_id: str | None = None,
        human_approved: bool = False,
        selected_alternative_index: int | None = None,
        prep_only: bool | None = None,
    ) -> CopilotChatResponse:
        with billing_ai_operation(org_id, feature="agents", operation_code="m38_copilot_chat"):
            return self._chat_inner(
                org_id,
                message=message,
                user_id=user_id,
                roles=roles,
                attrs=attrs,
                world_state=world_state,
                goal_id=goal_id,
                human_approved=human_approved,
                selected_alternative_index=selected_alternative_index,
                prep_only=prep_only,
            )

    def _chat_inner(
        self,
        org_id: str,
        *,
        message: str,
        user_id: str,
        roles: list[str] | None,
        attrs: dict | None,
        world_state: WorldState | None,
        goal_id: str | None,
        human_approved: bool,
        selected_alternative_index: int | None,
        prep_only: bool | None = None,
    ) -> CopilotChatResponse:
        # Wave 4 — resolve world state from UI publish + persisted goal session
        ws = build_world_state(
            org_id,
            roles=roles,
            user_id=user_id,
            goal_id=goal_id,
            explicit=world_state,
        )

        # Wave 3 — AI Firewall + abuse rate limit before any planning/retrieval
        try:
            ai_abuse_guard.check_chat_rate(org_id=org_id, user_id=user_id)
            message = ai_firewall.enforce(
                message, org_id=org_id, user_id=user_id, stage="user_prompt", goal_id=goal_id
            )
        except AIFirewallError as exc:
            decision = exc.decision
            return CopilotChatResponse(
                goal_id=goal_id or "",
                goal_run_id="",
                status="blocked_by_firewall",
                assistant_message=decision.reason or "Request blocked by AI security firewall.",
                mode="security_blocked",
                plan=PlanMetadata(
                    reasoning=f"Firewall detections: {', '.join(decision.detections)}",
                    confidence=0.0,
                    confidence_band="manual",
                    risk_level="high",
                ),
                approval_required=False,
                progress_percent=0.0,
                context_summary={"firewall": decision.to_dict()},
            )
        except AIBudgetExceeded as exc:
            return CopilotChatResponse(
                goal_id=goal_id or "",
                goal_run_id="",
                status="rate_limited",
                assistant_message=str(exc),
                mode="rate_limited",
                plan=PlanMetadata(reasoning=str(exc), confidence=0.0, risk_level="low"),
                approval_required=False,
                progress_percent=0.0,
            )

        if goal_id and message.strip().lower() in {"continue", "/continue", "resume"} and not human_approved and selected_alternative_index is None:
            goal = goal_repository.get_goal(org_id, goal_id)
            if not goal:
                raise ValueError("Goal not found")
            latest = goal_repository.get_latest_run(org_id, goal_id)
            if latest and latest.get("status") in {"pending_approval", "blocked", "running", "paused"}:
                return self.resume_run(
                    org_id,
                    goal_id=goal_id,
                    run_id=latest["id"],
                    user_id=user_id,
                    roles=roles,
                    attrs={**(attrs or {}), "user_id": user_id},
                    human_approved=False,
                )

        platform_ctx: PlatformContext | None = None
        if settings.m38_context_engine_enabled:
            with otel_span("m38.platform_context_engine.build", goal_id=goal_id or "", user_id=user_id):
                platform_ctx = platform_context_engine.build(
                    org_id,
                    message=message,
                    world_state=ws,
                    goal_id=goal_id,
                    user_id=user_id,
                    roles=roles,
                    attrs={**(attrs or {}), "user_id": user_id},
                )
            # Prefer engine-resolved world state (merged UI + session)
            if platform_ctx is not None:
                ws = platform_ctx.world_state
            ws = enrich_world_state_from_context(ws, platform_ctx)

        # AI-02: never plan mutates when entity clarification is required
        if (
            platform_ctx
            and getattr(platform_ctx, "clarification_required", False)
            and not human_approved
            and selected_alternative_index is None
        ):
            prompt = getattr(platform_ctx, "clarification_prompt", None) or "Please clarify which entity you mean."
            return CopilotChatResponse(
                goal_id=goal_id or "",
                goal_run_id="",
                status="needs_clarification",
                assistant_message=prompt,
                mode="needs_clarification",
                plan=PlanMetadata(
                    reasoning="Entity resolution below confidence threshold — no auto-bind",
                    confidence=0.0,
                    confidence_band="manual",
                    risk_level="low",
                ),
                approval_required=False,
                progress_percent=0.0,
                context_summary={
                    "entity_resolution": (
                        platform_ctx.entity_resolution.model_dump()
                        if getattr(platform_ctx, "entity_resolution", None)
                        else None
                    ),
                    "intent": platform_ctx.intent.intent if platform_ctx.intent else None,
                },
            )

        if (
            platform_ctx
            and settings.m38_read_answer_mode
            and platform_ctx.intent.intent in {"read", "analysis"}
            and not human_approved
            and selected_alternative_index is None
        ):
            return self._answer_read(
                org_id,
                message=message,
                user_id=user_id,
                world_state=ws,
                platform_ctx=platform_ctx,
                goal_id=goal_id,
            )

        if (
            platform_ctx
            and platform_ctx.intent.intent == "mixed"
            and settings.m38_read_answer_mode
            and not human_approved
        ):
            answer_out = answer_synthesizer.synthesize(org_id, platform_ctx, message)
            mixed_prefix = answer_out.get("answer", "") + "\n\n---\nProposed actions:\n"
        else:
            mixed_prefix = None

        # AI-04: notify planner of incomplete retrieval via message note (planner decides)
        if platform_ctx and getattr(platform_ctx, "retrieval_complete", True) is False and getattr(platform_ctx, "retrieval_failures", None):
            fail_note = f"\n[retrieval_incomplete failures={len(platform_ctx.retrieval_failures)}]"
            message = f"{message}{fail_note}"
            if mixed_prefix:
                mixed_prefix = f"{mixed_prefix}{fail_note}"
            log_event(
                "m38.planner.retrieval_incomplete",
                org_id=org_id,
                goal_id=goal_id or "",
                failure_count=len(platform_ctx.retrieval_failures),
            )

        title = message.strip()[:200]
        skip_retrieval = bool(platform_ctx and platform_ctx.summaries)
        # Wave 5: prep_only from API, attrs, or message marker
        effective_prep = bool(
            prep_only
            or (attrs or {}).get("prep_only")
            or "[prep-only]" in message.lower()
            or getattr(settings, "m38_default_prep_only", False)
        )
        graph, plan_meta = goal_planner.plan(
            message,
            world_state=ws,
            platform_context=platform_ctx,
            skip_retrieval_steps=skip_retrieval,
            org_id=org_id,
            user_id=user_id,
            prep_only=effective_prep,
            goal_id=goal_id,
        )

        goal_type = str((attrs or {}).get("goal_type") or "user")
        if goal_id:
            goal = goal_repository.get_goal(org_id, goal_id)
            if not goal:
                raise ValueError("Goal not found")
        else:
            goal = goal_repository.create_goal(
                org_id,
                title=title,
                description=message,
                trigger_type=str((attrs or {}).get("trigger_type") or "chat"),
                world_state=ws.model_dump(),
                plan_metadata=plan_meta.model_dump(),
                created_by=user_id,
                goal_type=goal_type,
                trigger_config={
                    "template_key": (attrs or {}).get("template_key"),
                    "prep_only": effective_prep,
                    "horizon": (attrs or {}).get("horizon"),
                },
            )
            goal_id = str(goal["id"])

        if platform_ctx and goal_id:
            try:
                platform_context_engine.persist_turn(org_id, goal_id, platform_ctx)
            except Exception as exc:
                log_event("m38.context.persist_failed", org_id=org_id, goal_id=goal_id, detail=str(exc))

        run = goal_repository.create_run(
            org_id,
            goal_id=goal_id,
            metadata={
                "message": message,
                "checkpoint": "planned",
                "cursor": 0,
                "prep_only": effective_prep,
                "estimated_completion": plan_meta.estimated_completion,
            },
            confidence_score=float(plan_meta.confidence),
            risk_level=plan_meta.risk_level,
        )
        run_id = str(run["id"])
        goal_repository.save_graph(
            org_id,
            goal_run_id=run_id,
            graph=graph.to_dict(),
            reasoning=plan_meta.reasoning,
            rollback_strategy=plan_meta.rollback_strategy,
        )

        if selected_alternative_index is not None:
            return self.apply_alternative(
                org_id,
                goal_id=goal_id,
                run_id=run_id,
                alternative_index=selected_alternative_index,
                user_id=user_id,
                roles=roles,
                attrs={**(attrs or {}), "user_id": user_id},
            )

        return self._execute_loop(
            org_id,
            goal_id=goal_id,
            run_id=run_id,
            graph=graph,
            plan_meta=plan_meta,
            world_state=ws,
            user_id=user_id,
            roles=roles,
            attrs={**(attrs or {}), "user_id": user_id, "prep_only": effective_prep},
            human_approved=human_approved,
            assistant_prefix=mixed_prefix or f"Plan for: {title}",
            platform_ctx=platform_ctx,
            prep_only=effective_prep,
        )

    def _answer_read(
        self,
        org_id: str,
        *,
        message: str,
        user_id: str,
        world_state: WorldState,
        platform_ctx: PlatformContext,
        goal_id: str | None,
    ) -> CopilotChatResponse:
        with otel_span("m38.answer_synthesizer", intent=platform_ctx.intent.intent):
            answer_out = answer_synthesizer.synthesize(org_id, platform_ctx, message)
        title = message.strip()[:200]

        if goal_id:
            goal = goal_repository.get_goal(org_id, goal_id)
            if not goal:
                raise ValueError("Goal not found")
        else:
            goal = goal_repository.create_goal(
                org_id,
                title=title,
                description=message,
                trigger_type="chat",
                world_state=world_state.model_dump(),
                plan_metadata={"reasoning": "read-only answer", "confidence": 85.0},
                created_by=user_id,
            )
            goal_id = str(goal["id"])

        run = goal_repository.create_run(
            org_id,
            goal_id=goal_id,
            metadata={"message": message, "mode": "answer"},
            confidence_score=85.0,
            risk_level="low",
        )
        run_id = str(run["id"])
        goal_repository.update_goal_status(org_id, goal_id, status="completed")
        goal_repository.update_run(org_id, run_id, status="completed", metadata={"mode": "answer"})
        platform_context_engine.persist_turn(org_id, goal_id, platform_ctx)

        return CopilotChatResponse(
            goal_id=goal_id,
            goal_run_id=run_id,
            status="completed",
            assistant_message=str(answer_out.get("answer") or ""),
            mode="answer",
            plan=PlanMetadata(
                reasoning="Answer synthesized from Platform Context Engine",
                confidence=85.0,
                confidence_band=str(answer_out.get("confidence_band") or "review"),
                risk_level="low",
            ),
            approval_required=False,
            progress_percent=100.0,
            sources=answer_out.get("sources") or {},
            context_summary={
                "summaries": list(platform_ctx.summaries.keys()),
                "intent": platform_ctx.intent.intent,
                "facts": answer_out.get("facts") or [],
                "data_gaps": answer_out.get("data_gaps") or [],
            },
        )

    def resume_run(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        user_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
        human_approved: bool = False,
    ) -> CopilotChatResponse:
        goal = goal_repository.get_goal(org_id, goal_id)
        if not goal:
            raise ValueError("Goal not found")
        run = goal_repository.get_run(org_id, run_id)
        if not run:
            raise ValueError("Goal run not found")
        graph_data = goal_repository.get_latest_graph(org_id, run_id)
        if not graph_data:
            raise ValueError("Execution graph not found")
        graph = ExecutionGraph.from_dict({"nodes": graph_data["nodes"], "edges": graph_data.get("edges") or []})
        recovered = _recover_interrupted_nodes(graph)
        plan_meta = PlanMetadata(**(goal.get("plan_metadata") or {}))
        ws = WorldState(**(goal.get("world_state") or {}))
        goal_repository.update_run(
            org_id,
            run_id,
            status="running",
            metadata={
                "checkpoint": "resumed",
                "recovery_executed": True,
                "recovered_running_nodes": recovered,
                "cursor": run.get("current_node_id"),
            },
        )
        goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict(), reasoning=plan_meta.reasoning)
        log_event(
            "m38.runtime.goal_resumed",
            org_id=org_id,
            goal_id=goal_id,
            run_id=run_id,
            recovered_running_nodes=recovered,
        )
        return self._execute_loop(
            org_id,
            goal_id=goal_id,
            run_id=run_id,
            graph=graph,
            plan_meta=plan_meta,
            world_state=ws,
            user_id=user_id,
            roles=roles,
            attrs={**(attrs or {}), "user_id": user_id},
            human_approved=human_approved,
            assistant_prefix="Resuming goal from checkpoint",
        )

    def approve_and_continue(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        user_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
    ) -> CopilotChatResponse:
        return self.resume_run(
            org_id,
            goal_id=goal_id,
            run_id=run_id,
            user_id=user_id,
            roles=roles,
            attrs=attrs,
            human_approved=True,
        )

    def apply_alternative(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        alternative_index: int,
        user_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
    ) -> CopilotChatResponse:
        observations = goal_repository.list_observations(org_id, run_id, limit=10)
        alts: list[dict] = []
        for obs in reversed(observations):
            if obs.get("alternatives"):
                alts = obs["alternatives"]
                break
        alt_node = self_correction.apply_alternative(alts, alternative_index)
        if not alt_node:
            raise ValueError("Invalid alternative index")
        graph_data = goal_repository.get_latest_graph(org_id, run_id)
        graph = ExecutionGraph.from_dict({"nodes": graph_data["nodes"], "edges": graph_data.get("edges") or []})
        graph.add_node(alt_node)
        goal = goal_repository.get_goal(org_id, goal_id)
        plan_meta = PlanMetadata(**(goal.get("plan_metadata") or {}))
        ws = WorldState(**(goal.get("world_state") or {}))
        goal_repository.update_run(org_id, run_id, status="running", human_approved=True)
        return self._execute_loop(
            org_id,
            goal_id=goal_id,
            run_id=run_id,
            graph=graph,
            plan_meta=plan_meta,
            world_state=ws,
            user_id=user_id,
            roles=roles,
            attrs={**(attrs or {}), "user_id": user_id},
            human_approved=True,
            assistant_prefix=f"Applying alternative {alternative_index + 1}",
        )

    def undo(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        user_id: str,
        steps: int = 1,
        roles: list[str] | None = None,
        attrs: dict | None = None,
    ) -> CopilotChatResponse:
        with billing_ai_operation(org_id, feature="agents", operation_code="m38_undo"):
            graph_data = goal_repository.get_latest_graph(org_id, run_id)
            if not graph_data:
                raise ValueError("Execution graph not found")
            graph = ExecutionGraph.from_dict({"nodes": graph_data["nodes"], "edges": graph_data.get("edges") or []})
            undo_graph = rollback_manager.build_undo_graph(graph, steps=steps)
            chain = rollback_manager.enrich_undo_plan(org_id, graph, undo_graph)
            plan_meta = PlanMetadata(
                reasoning="Rollback/compensation plan",
                confidence=70.0,
                confidence_band="review",
                risk_level="medium",
                rollback_strategy=chain,
            )
            ws = WorldState()
            log_event(
                "m38.runtime.compensation_plan",
                org_id=org_id,
                goal_id=goal_id,
                run_id=run_id,
                undo_nodes=len(undo_graph.nodes),
                compensation_executed=False,
            )
            return self._execute_loop(
                org_id,
                goal_id=goal_id,
                run_id=run_id,
                graph=undo_graph,
                plan_meta=plan_meta,
                world_state=ws,
                user_id=user_id,
                roles=roles,
                attrs={**(attrs or {}), "user_id": user_id},
                human_approved=True,
                assistant_prefix="Undo plan",
            )

    def _audit_step(
        self,
        org_id: str,
        *,
        run_id: str,
        node: GraphNodeSpec,
        obs: ObservationResult,
        user_id: str,
        failure: dict | None = None,
        latency_ms: float | None = None,
        retries: int = 0,
    ) -> None:
        payload = {
            "tool": node.tool,
            "method": node.method,
            "status": obs.status,
            "success": obs.success,
            "user_id": user_id,
            "latency_ms": latency_ms,
            "retries": retries,
            "compensation_tool": node.compensation_tool,
            "failure": failure,
        }
        audit_repo.create_log(
            org_id=org_id,
            actor_type="agent",
            actor_id="platform_ai_runtime",
            event_type="m38.goal.step",
            object_ref=f"goal_run:{run_id}:{node.id}",
            payload_jsonb=payload,
        )
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="agent",
                actor_id=user_id,
                action="m38.goal.step",
                object_ref=f"goal_run:{run_id}:{node.id}",
                payload=payload,
                entity_type=node.tool,
                entity_id=node.id,
                source_service="platform_ai_runtime",
            )
        except Exception as exc:
            log_event("m38.audit.step_governance_failed", org_id=org_id, detail=str(exc))

    def _execute_loop(
        self,
        org_id: str,
        *,
        goal_id: str,
        run_id: str,
        graph: ExecutionGraph,
        plan_meta: PlanMetadata,
        world_state: WorldState,
        user_id: str,
        roles: list[str] | None,
        attrs: dict,
        human_approved: bool,
        assistant_prefix: str,
        platform_ctx: PlatformContext | None = None,
        prep_only: bool = False,
    ) -> CopilotChatResponse:
        observations: list[ObservationResult] = []
        steps = 0
        mode = "executing"
        approval_required = False
        assistant_message = (
            plan_meta.collaboration_message
            or plan_meta.reasoning
            or assistant_prefix
        )
        prep_only = prep_only or bool(attrs.get("prep_only")) or bool(plan_meta.prep_only)
        compensation_engine.attach_missing_compensations(graph)
        rollback_chain = rollback_manager.record_compensation_chain(graph)
        node_retries: dict[str, int] = {}
        max_steps = _max_steps()
        max_retries = _max_node_retries()
        recovered = _recover_interrupted_nodes(graph)
        if recovered:
            log_event("m38.runtime.recovered_running_nodes", org_id=org_id, goal_id=goal_id, count=recovered)
        ai_abuse_guard.start_run(run_id=run_id)
        recommendations: list[dict] = []

        try:
            while steps < max_steps and not graph.all_complete():
                node = graph.next_ready_node()
                if not node:
                    if graph.has_failed():
                        break
                    break

                needs_approval = node.requires_approval and not tool_registry.is_read_only(node.tool, node.method)
                mutates = not tool_registry.is_read_only(node.tool, node.method)
                # Wave 5 autonomy governance — never mutate financial truth without approval
                from app.modules.finance_os.platform_ai_runtime.autonomy.governance import autonomy_governance

                gate = autonomy_governance.assert_mutates_only_with_approval(
                    human_approved=human_approved,
                    prep_only=prep_only or node.prep_only,
                    mutates=mutates,
                )
                if not gate["allowed"]:
                    mode = "plan_pending_approval"
                    approval_required = True
                    assistant_message = (
                        plan_meta.collaboration_message
                        or gate["detail"]
                        or f"Approval required before: {node.label}"
                    )
                    node.status = "pending"
                    goal_repository.update_run(
                        org_id,
                        run_id,
                        status="pending_approval",
                        current_node_id=node.id,
                        metadata={
                            "checkpoint": node.id,
                            "approval_wait": True,
                            "cursor": node.id,
                            "prep_only": True,
                            "autonomy_gate": gate,
                        },
                    )
                    goal_repository.save_graph(
                        org_id, goal_run_id=run_id, graph=graph.to_dict(), reasoning=plan_meta.reasoning
                    )
                    break

                if needs_approval and not human_approved:
                    mode = "plan_pending_approval"
                    approval_required = True
                    assistant_message = (
                        plan_meta.collaboration_message or f"Approval required before: {node.label}"
                    )
                    goal_repository.update_run(
                        org_id,
                        run_id,
                        status="pending_approval",
                        current_node_id=node.id,
                        metadata={"checkpoint": node.id, "approval_wait": True, "cursor": node.id},
                    )
                    goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict(), reasoning=plan_meta.reasoning)
                    log_event(
                        "m38.runtime.approval_wait",
                        org_id=org_id,
                        goal_id=goal_id,
                        run_id=run_id,
                        node_id=node.id,
                        tool=f"{node.tool}.{node.method}",
                    )
                    break

                graph.mark_running(node.id)
                started = time.perf_counter()
                latency_ms = 0.0
                result: dict = {}
                with otel_span(
                    "m38.tool_step",
                    tool=node.tool,
                    method=node.method,
                    goal_id=goal_id,
                    node_id=node.id,
                    run_id=run_id,
                    retries=node_retries.get(node.id, 0),
                ):
                    with billing_ai_operation(org_id, feature="agents", operation_code=f"m38_tool.{node.tool}.{node.method}"):
                        try:
                            ai_abuse_guard.check_tool_step(run_id=run_id, org_id=org_id)
                            result = executor.run(
                                org_id,
                                tool=node.tool,
                                method=node.method,
                                params=node.params,
                                actor_id=user_id,
                                roles=roles,
                                attrs=attrs,
                                human_approved=human_approved or not needs_approval,
                            )
                        except AIBudgetExceeded as exc:
                            result = {
                                "status": "error",
                                "detail": str(exc),
                                "retryable": False,
                                "failure_class": FailureClass.POLICY.value,
                                "code": "AI_BUDGET_EXCEEDED",
                            }
                            mode = "failed"
                            assistant_message = str(exc)
                            graph.mark_failed(node.id)
                            goal_repository.update_run(org_id, run_id, status="failed", current_node_id=node.id)
                            break
                        except Exception as exc:
                            cf = classify_exception(exc, context="execution")
                            result = {
                                "status": "error",
                                "detail": cf.message,
                                "retryable": cf.retryable,
                                "failure_class": cf.failure_class.value,
                                "code": cf.code,
                            }
                            log_event(
                                "m38.runtime.node_exception",
                                org_id=org_id,
                                goal_id=goal_id,
                                run_id=run_id,
                                node_id=node.id,
                                **cf.to_dict(),
                            )
                        finally:
                            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)

                if str(result.get("status")) == "pending_approval":
                    mode = "plan_pending_approval"
                    approval_required = True
                    assistant_message = f"Step '{node.label}' requires approval."
                    node.status = "pending"
                    goal_repository.update_run(
                        org_id,
                        run_id,
                        status="pending_approval",
                        current_node_id=node.id,
                        metadata={"checkpoint": node.id, "approval_wait": True},
                    )
                    goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict())
                    break

                obs = observer.analyze(node, result, world_state=world_state)
                classified = classify_tool_result(result, node_id=node.id, tool=node.tool, method=node.method)
                if classified and not obs.success:
                    if classified.retryable:
                        obs.retryable = True
                    result_payload = dict(obs.raw_result or result)
                    result_payload["failure"] = classified.to_dict()
                    obs.raw_result = result_payload

                retries_so_far = node_retries.get(node.id, 0)
                observations.append(obs)
                self._audit_step(
                    org_id,
                    run_id=run_id,
                    node=node,
                    obs=obs,
                    user_id=user_id,
                    failure=classified.to_dict() if classified and not obs.success else None,
                    latency_ms=latency_ms,
                    retries=retries_so_far,
                )
                goal_repository.save_observation(
                    org_id,
                    goal_run_id=run_id,
                    node_id=node.id,
                    tool_name=node.tool,
                    tool_method=node.method,
                    status=obs.status,
                    result={
                        **(obs.raw_result or {}),
                        "latency_ms": latency_ms,
                        "retries": retries_so_far,
                        "failure": classified.to_dict() if classified and not obs.success else None,
                    },
                    alternatives=obs.alternatives,
                )
                log_event(
                    "m38.runtime.node",
                    org_id=org_id,
                    goal_id=goal_id,
                    run_id=run_id,
                    node_id=node.id,
                    tool=node.tool,
                    method=node.method,
                    latency_ms=latency_ms,
                    retries=retries_so_far,
                    success=obs.success,
                    status=obs.status,
                    failure_class=classified.failure_class.value if classified and not obs.success else None,
                    compensation_tool=node.compensation_tool,
                )

                if obs.success:
                    graph.mark_complete(node.id)
                    if result.get("entity_id"):
                        world_state = refresh_after_step(org_id, world_state, {"entity_id": result["entity_id"]})
                        node.params.setdefault("entity_id", result["entity_id"])
                        if node.tool == "procurement" and node.method == "create_po":
                            node.params["po_id"] = result["entity_id"]
                        if node.method == "create_grn":
                            node.params["grn_id"] = result.get("entity_id")
                        if node.tool == "journals" and node.method == "create_draft":
                            node.params["journal_id"] = result.get("entity_id")
                        if node.tool == "ap" and "invoice" in node.method:
                            node.params.setdefault("invoice_id", result.get("entity_id"))
                else:
                    correction = self_correction.suggest(obs)
                    can_auto_retry = (
                        correction.get("action") == "retry"
                        and correction.get("auto")
                        and retries_so_far < max_retries
                        and (obs.retryable or (classified is not None and classified.retryable))
                    )
                    if can_auto_retry:
                        node_retries[node.id] = retries_so_far + 1
                        node.status = "pending"
                        log_event(
                            "m38.runtime.node_retry",
                            org_id=org_id,
                            goal_id=goal_id,
                            run_id=run_id,
                            node_id=node.id,
                            attempt=node_retries[node.id],
                            max_retries=max_retries,
                            failure_class=classified.failure_class.value if classified else None,
                        )
                        goal_repository.update_run(
                            org_id,
                            run_id,
                            metadata={
                                "checkpoint": node.id,
                                "retry_position": node.id,
                                "node_retries": dict(node_retries),
                            },
                        )
                        continue
                    if correction.get("action") == "present_alternatives":
                        graph.mark_failed(node.id)
                        mode = "blocked"
                        approval_required = True
                        assistant_message = obs.reason or "Blocked — choose an alternative."
                        goal_repository.update_run(org_id, run_id, status="blocked", current_node_id=node.id)
                        goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict())
                        break
                    graph.mark_failed(node.id)
                    mode = "failed"
                    assistant_message = obs.reason or (classified.message if classified else "Step failed.")
                    if classified:
                        assistant_message = f"[{classified.failure_class.value}] {assistant_message}"
                    goal_repository.update_run(
                        org_id,
                        run_id,
                        status="failed",
                        current_node_id=node.id,
                        metadata={
                            "checkpoint": node.id,
                            "failure": classified.to_dict() if classified else {"message": assistant_message},
                        },
                    )
                    goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict())
                    break

                steps += 1
                goal_repository.update_run(
                    org_id,
                    run_id,
                    current_node_id=node.id,
                    metadata={
                        "checkpoint": node.id,
                        "steps_completed": steps,
                        "cursor": node.id,
                        "node_retries": dict(node_retries),
                    },
                )
                goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict(), reasoning=plan_meta.reasoning)

            if steps >= max_steps and not graph.all_complete() and mode not in {"failed", "blocked", "plan_pending_approval"}:
                mode = "paused"
                assistant_message = (
                    f"Execution paused after {max_steps} steps "
                    f"(configurable via M38_MAX_RUNTIME_STEPS). Resume to continue pending nodes."
                )
                goal_repository.update_run(
                    org_id,
                    run_id,
                    status="paused",
                    metadata={"checkpoint": "step_limit", "steps_completed": steps, "max_steps": max_steps},
                )
                goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict())
                log_event(
                    "m38.runtime.step_limit",
                    org_id=org_id,
                    goal_id=goal_id,
                    run_id=run_id,
                    steps=steps,
                    max_steps=max_steps,
                )
        finally:
            ai_abuse_guard.finish_run(run_id=run_id)

        progress = _graph_progress(graph)
        completed_nodes = [n.id for n in graph.nodes.values() if n.status in {"completed", "skipped"}]
        pending_nodes = [n.id for n in graph.nodes.values() if n.status in {"pending", "running"}]
        if graph.all_complete() and not approval_required and mode not in {"failed", "blocked", "paused"}:
            mode = "completed"
            # Operational long-running goals stay active for future event cycles (Wave 5)
            goal_row = goal_repository.get_goal(org_id, goal_id) or {}
            gtype = str(goal_row.get("goal_type") or "user")
            if gtype in {"operational", "scheduled", "watching"}:
                goal_repository.update_goal_status(org_id, goal_id, status="active")
            else:
                goal_repository.update_goal_status(org_id, goal_id, status="completed")
            goal_repository.update_run(org_id, run_id, status="completed", metadata={"checkpoint": "completed"})
            assistant_message = (
                plan_meta.collaboration_message
                or f"Goal completed in {steps} step(s). {plan_meta.reasoning}"
            )
            try:
                from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

                goal_manager.write_outcome_memory(
                    org_id, goal_id=goal_id, run_id=run_id, summary=assistant_message[:500],
                )
            except Exception as exc:
                log_event("m38.memory.outcome_failed", org_id=org_id, goal_id=goal_id, detail=str(exc))
            try:
                from app.modules.finance_os.platform_ai_runtime.autonomy.organizational_learning import (
                    organizational_learning,
                )
                from app.modules.finance_os.platform_ai_runtime.autonomy.recommendation_engine import (
                    autonomy_recommendation_engine,
                )

                organizational_learning.observe_run(
                    org_id,
                    goal_id=goal_id,
                    run_id=run_id,
                    observations=[o.model_dump() for o in observations],
                    plan_meta=plan_meta.model_dump(),
                )
                rec = autonomy_recommendation_engine.from_plan(plan_meta, world_state=world_state)
                soft = autonomy_recommendation_engine.persist_soft(org_id, run_id=run_id, rec=rec)
                if soft:
                    recommendations.append(soft if isinstance(soft, dict) else rec.model_dump())
            except Exception as exc:
                log_event("m38.learning.or_recommendation_failed", org_id=org_id, detail=str(exc))

        if platform_ctx and goal_id:
            try:
                platform_context_engine.persist_turn(org_id, goal_id, platform_ctx)
            except Exception as exc:
                log_event("m38.context.persist_failed", org_id=org_id, goal_id=goal_id, detail=str(exc))

        audit_repo.create_log(
            org_id=org_id,
            actor_type="agent",
            actor_id="platform_ai_runtime",
            event_type="m38.goal.run",
            object_ref=f"goal_run:{run_id}",
            payload_jsonb={
                "status": mode,
                "steps": steps,
                "goal_id": goal_id,
                "progress": progress,
                "node_retries": node_retries,
                "max_steps": max_steps,
                "prep_only": prep_only,
                "envelope": plan_meta.envelope.model_dump() if plan_meta.envelope else None,
            },
        )
        log_event(
            "m38.runtime.run_complete",
            org_id=org_id,
            goal_id=goal_id,
            run_id=run_id,
            status=mode,
            steps=steps,
            progress=progress,
            approval_required=approval_required,
            prep_only=prep_only,
        )

        from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GoalProgressSnapshot

        return CopilotChatResponse(
            goal_id=goal_id,
            goal_run_id=run_id,
            status=mode,
            assistant_message=assistant_message,
            mode=mode,
            plan=plan_meta,
            graph_nodes=list(graph.nodes.values()),
            observations=observations,
            approval_required=approval_required,
            progress_percent=progress,
            pending_approval_nodes=_pending_approval_nodes(graph),
            rollback_chain=rollback_chain,
            collaboration_message=plan_meta.collaboration_message,
            recommendations=recommendations,
            envelope=plan_meta.envelope,
            progress=GoalProgressSnapshot(
                goal_id=goal_id,
                run_id=run_id,
                current_node_id=next((n.id for n in graph.nodes.values() if n.status == "running"), None)
                or (pending_nodes[0] if pending_nodes else None),
                completed_nodes=completed_nodes,
                pending_nodes=pending_nodes,
                approval_state=mode if approval_required else None,
                checkpoint=completed_nodes[-1] if completed_nodes else "planned",
                progress_percent=progress,
                risk_level=plan_meta.risk_level,
                estimated_completion=plan_meta.estimated_completion,
                steps_completed=steps,
            ),
        )


runtime_service = RuntimeService()
