from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.engine.execution_graph import ExecutionGraph
from app.modules.finance_os.platform_ai_runtime.engine.goal_planner import goal_planner
from app.modules.finance_os.platform_ai_runtime.engine.observer import observer
from app.modules.finance_os.platform_ai_runtime.engine.rollback_manager import rollback_manager
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
from app.modules.platform.billing.billing_hooks import billing_ai_operation
from app.services.otel import otel_span
from app.services.repositories import audit_repo

MAX_RUNTIME_STEPS = 25


def _graph_progress(graph: ExecutionGraph) -> float:
    if not graph.nodes:
        return 0.0
    done = sum(1 for n in graph.nodes.values() if n.status in {"completed", "skipped"})
    return round(100.0 * done / len(graph.nodes), 1)


def _pending_approval_nodes(graph: ExecutionGraph) -> list[str]:
    return [n.id for n in graph.pending_approval_nodes()]


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
    ) -> CopilotChatResponse:
        ws = world_state or build_world_state(org_id, payload={"world_state": {}}, roles=roles, user_id=user_id)

        if goal_id and message.strip().lower() in {"continue", "/continue", "resume"} and not human_approved and selected_alternative_index is None:
            goal = goal_repository.get_goal(org_id, goal_id)
            if not goal:
                raise ValueError("Goal not found")
            latest = goal_repository.get_latest_run(org_id, goal_id)
            if latest and latest.get("status") in {"pending_approval", "blocked", "running"}:
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
                )
            ws = enrich_world_state_from_context(ws, platform_ctx)

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

        title = message.strip()[:200]
        skip_retrieval = bool(platform_ctx and platform_ctx.summaries)
        graph, plan_meta = goal_planner.plan(
            message,
            world_state=ws,
            platform_context=platform_ctx,
            skip_retrieval_steps=skip_retrieval,
        )

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
                world_state=ws.model_dump(),
                plan_metadata=plan_meta.model_dump(),
                created_by=user_id,
            )
            goal_id = str(goal["id"])

        if platform_ctx and goal_id:
            try:
                platform_context_engine.persist_turn(org_id, goal_id, platform_ctx)
            except Exception:
                pass

        run = goal_repository.create_run(
            org_id,
            goal_id=goal_id,
            metadata={"message": message, "checkpoint": "planned"},
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
            attrs={**(attrs or {}), "user_id": user_id},
            human_approved=human_approved,
            assistant_prefix=mixed_prefix or f"Plan for: {title}",
            platform_ctx=platform_ctx,
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
            context_summary={"summaries": list(platform_ctx.summaries.keys()), "intent": platform_ctx.intent.intent},
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
        plan_meta = PlanMetadata(**(goal.get("plan_metadata") or {}))
        ws = WorldState(**(goal.get("world_state") or {}))
        goal_repository.update_run(org_id, run_id, status="running", metadata={"checkpoint": "resumed"})
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

    def _audit_step(self, org_id: str, *, run_id: str, node: GraphNodeSpec, obs: ObservationResult, user_id: str) -> None:
        audit_repo.create_log(
            org_id=org_id,
            actor_type="agent",
            actor_id="platform_ai_runtime",
            event_type="m38.goal.step",
            object_ref=f"goal_run:{run_id}:{node.id}",
            payload_jsonb={
                "tool": node.tool,
                "method": node.method,
                "status": obs.status,
                "success": obs.success,
                "user_id": user_id,
            },
        )
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="agent",
                actor_id=user_id,
                action="m38.goal.step",
                object_ref=f"goal_run:{run_id}:{node.id}",
                payload={"tool": f"{node.tool}.{node.method}", "status": obs.status},
                entity_type=node.tool,
                entity_id=node.id,
                source_service="platform_ai_runtime",
            )
        except Exception:
            pass

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
    ) -> CopilotChatResponse:
        observations: list[ObservationResult] = []
        steps = 0
        mode = "executing"
        approval_required = False
        assistant_message = plan_meta.reasoning or assistant_prefix
        rollback_chain = rollback_manager.record_compensation_chain(graph)

        while steps < MAX_RUNTIME_STEPS and not graph.all_complete():
            node = graph.next_ready_node()
            if not node:
                if graph.has_failed():
                    break
                break

            needs_approval = node.requires_approval and not tool_registry.is_read_only(node.tool, node.method)
            if needs_approval and not human_approved:
                mode = "plan_pending_approval"
                approval_required = True
                assistant_message = f"Approval required before: {node.label}"
                goal_repository.update_run(org_id, run_id, status="pending_approval", current_node_id=node.id, metadata={"checkpoint": node.id})
                goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict(), reasoning=plan_meta.reasoning)
                break

            graph.mark_running(node.id)
            with otel_span("m38.tool_step", tool=node.tool, method=node.method, goal_id=goal_id):
                with billing_ai_operation(org_id, feature="agents", operation_code=f"m38_tool.{node.tool}.{node.method}"):
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

            if str(result.get("status")) == "pending_approval":
                mode = "plan_pending_approval"
                approval_required = True
                assistant_message = f"Step '{node.label}' requires approval."
                goal_repository.update_run(org_id, run_id, status="pending_approval", current_node_id=node.id)
                goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict())
                break

            obs = observer.analyze(node, result, world_state=world_state)
            observations.append(obs)
            self._audit_step(org_id, run_id=run_id, node=node, obs=obs, user_id=user_id)
            goal_repository.save_observation(
                org_id,
                goal_run_id=run_id,
                node_id=node.id,
                tool_name=node.tool,
                tool_method=node.method,
                status=obs.status,
                result=obs.raw_result,
                alternatives=obs.alternatives,
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
            else:
                correction = self_correction.suggest(obs)
                if correction.get("action") == "retry" and correction.get("auto"):
                    continue
                if correction.get("action") == "present_alternatives":
                    graph.mark_failed(node.id)
                    mode = "blocked"
                    approval_required = True
                    assistant_message = obs.reason or "Blocked — choose an alternative."
                    goal_repository.update_run(org_id, run_id, status="blocked", current_node_id=node.id)
                    break
                graph.mark_failed(node.id)
                mode = "failed"
                assistant_message = obs.reason or "Step failed."
                goal_repository.update_run(org_id, run_id, status="failed", current_node_id=node.id)
                break

            steps += 1
            goal_repository.update_run(org_id, run_id, metadata={"checkpoint": node.id, "steps_completed": steps})
            goal_repository.save_graph(org_id, goal_run_id=run_id, graph=graph.to_dict(), reasoning=plan_meta.reasoning)

        progress = _graph_progress(graph)
        if graph.all_complete() and not approval_required:
            mode = "completed"
            goal_repository.update_goal_status(org_id, goal_id, status="completed")
            goal_repository.update_run(org_id, run_id, status="completed", metadata={"checkpoint": "completed"})
            assistant_message = f"Goal completed in {steps} step(s). {plan_meta.reasoning}"
            try:
                from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager

                goal_manager.write_outcome_memory(
                    org_id, goal_id=goal_id, run_id=run_id, summary=assistant_message[:500],
                )
            except Exception:
                pass

        if platform_ctx and goal_id:
            try:
                platform_context_engine.persist_turn(org_id, goal_id, platform_ctx)
            except Exception:
                pass

        audit_repo.create_log(
            org_id=org_id,
            actor_type="agent",
            actor_id="platform_ai_runtime",
            event_type="m38.goal.run",
            object_ref=f"goal_run:{run_id}",
            payload_jsonb={"status": mode, "steps": steps, "goal_id": goal_id, "progress": progress},
        )

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
        )


runtime_service = RuntimeService()
