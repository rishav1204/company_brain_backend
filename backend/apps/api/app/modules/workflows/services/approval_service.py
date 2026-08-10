from __future__ import annotations

from app.modules.workflows.engine.transition_engine import apply_transition
from app.modules.workflows.engine.workflow_state_machine import status_to_legacy_state
from datetime import datetime, timezone

from app.modules.workflows.events.workflow_events import (
    audit_transition,
    emit_approval_completed,
    emit_approval_rejected,
    emit_workflow_advance_requested,
)
from app.modules.workflows.repositories import approval_repo, step_repo, task_repo, workflow_repo
from app.modules.workflows.repositories.workflow_uow import workflow_uow
from app.modules.workflows.services.workflow_observability import record_approval
from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator
from app.modules.workflows.services.workflow_policy_service import validate_approval_authority
from app.services.object_context import resolve_object_context
from app.services.repositories import workflows_repo


class ApprovalService:
    def request_approval(
        self,
        *,
        org_id: str,
        instance_id: str,
        step_id: str,
        requested_from: str | None,
        level: int = 1,
        amount_threshold: float | None = None,
        trace_id: str | None = None,
    ) -> dict:
        instance = workflow_repo.get_instance(org_id, instance_id) or {}
        step = next((s for s in step_repo.list_steps(org_id, instance_id) if s["id"] == step_id), {"id": step_id})
        return workflow_orchestrator.start_approval_chain(
            org_id=org_id,
            instance=instance,
            step=step,
            trace_id=trace_id,
        )

    def decide(
        self,
        *,
        org_id: str,
        user_id: str,
        roles: list[str],
        attrs: dict | None,
        approval_id: str,
        decision: str,
        reason: str | None = None,
        delegate_to: str | None = None,
        trace_id: str | None = None,
    ) -> dict:
        approval = approval_repo.get_approval(org_id, approval_id)
        if not approval:
            raise ValueError("Approval not found")
        if approval.get("decision") != "pending":
            raise ValueError("Approval already decided")
        instance = workflow_repo.get_instance(org_id, approval["workflow_instance_id"])
        if not instance:
            raise ValueError("Workflow instance not found")

        normalized = decision.strip().lower()
        if normalized == "delegated":
            return self._delegate(org_id, approval, instance, delegate_to, trace_id=trace_id)
        if normalized == "expired":
            return self._expire(org_id, approval, instance, trace_id=trace_id)

        metadata = instance.get("metadata") or {}
        amount = metadata.get("amount")
        object_context = resolve_object_context(
            org_id=org_id,
            object_type="workflow",
            object_id=instance.get("legacy_workflow_id") or instance["id"],
        )
        if amount is not None:
            try:
                object_context.amount = float(amount)
            except (TypeError, ValueError):
                pass
        action = "approve" if normalized in {"approved", "approve"} else "reject"
        if normalized in {"approved", "approve"}:
            try:
                from app.modules.platform.governance.services.policy_service import governance_policy_service

                gov = governance_policy_service.evaluate(
                    org_id,
                    action="invoice.approve",
                    attrs={**(attrs or {}), "amount": amount},
                    roles=roles,
                    created_by=instance.get("started_by"),
                    actor_user_id=user_id,
                )
                if not gov.allowed:
                    raise PermissionError(gov.reason or "Governance policy denied")
                dup = governance_policy_service.check_duplicate_payment(
                    org_id,
                    payment_id=approval_id,
                    amount=float(amount or 0),
                    vendor_id=str(metadata.get("vendor_id", "")),
                )
                if dup:
                    from app.modules.platform.governance.services.compliance_service import compliance_service

                    compliance_service.track_approval_bypass(
                        org_id,
                        entity_type="approval",
                        entity_id=approval_id,
                        actor_id=user_id,
                        reason=dup,
                    )
                    raise PermissionError(dup)
            except PermissionError:
                raise
            except Exception:
                pass
        allowed, deny_reason = validate_approval_authority(
            org_id=org_id,
            user_id=user_id,
            roles=roles,
            action=action,
            object_context=object_context,
            attrs=attrs,
            created_by=instance.get("started_by"),
            human_approved=normalized in {"approved", "approve"},
        )
        if not allowed:
            raise PermissionError(deny_reason or "Approval denied")

        with workflow_uow(org_id) as uow:
            row = uow.decide_approval(
                approval_id,
                approver_user_id=user_id,
                decision="approved" if normalized in {"approved", "approve"} else "rejected",
                reason=reason,
            )
            if not row:
                raise ValueError("Approval update failed")
            step_id = row.get("workflow_step_id")
            if step_id:
                uow.update_step(
                    step_id,
                    status="approved" if row["decision"] == "approved" else "rejected",
                    completed=True,
                )
            if row["decision"] == "approved":
                uow.update_instance(
                    row["workflow_instance_id"],
                    status=apply_transition(
                        current_status=instance.get("status") or "waiting_approval",
                        target_status="approved",
                    ),
                )

        record_approval(row.get("decision", normalized))
        try:
            from app.modules.platform.governance.explainability.evidence_linker import auto_link_entity_evidence

            auto_link_entity_evidence(
                org_id,
                entity_type="approval",
                entity_id=approval_id,
                evidence_type="workflow_instance",
                evidence_ref=row["workflow_instance_id"],
                metadata={"decision": row.get("decision")},
            )
        except Exception:
            pass
        instance_id = row["workflow_instance_id"]
        level = int(row.get("level") or 1)
        created_at = approval.get("created_at")
        if created_at and isinstance(created_at, datetime):
            from app.modules.workflows.services.workflow_observability import record_approval_wait

            wait_ms = int((datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)).total_seconds() * 1000)
            record_approval_wait(org_id, approval_id, wait_ms)

        if row["decision"] == "approved":
            emit_approval_completed(org_id, approval_id, "approved", trace_id=trace_id)
            emit_workflow_advance_requested(
                org_id, instance_id, decided_level=level, approval_id=approval_id, trace_id=trace_id
            )
            # INT-12: persist approval identity/roles into workflow metadata for execution-time policy checks.
            try:
                inst = workflow_repo.get_instance(org_id, instance_id) or instance
                meta = dict(inst.get("metadata") or {})
                meta.update(
                    {
                        "approved_by": user_id,
                        "approved_roles": roles,
                        "approved_at": datetime.now(timezone.utc).isoformat(),
                        "approved_via": "workflow.approval",
                        "approval_id": approval_id,
                        "approval_level": level,
                    }
                )
                with workflow_uow(org_id) as uow:
                    uow.update_instance(instance_id, metadata=meta)
            except Exception:
                pass
            from app.services.event_consumers import _consume_workflow_approval_event

            result = _consume_workflow_approval_event(
                {
                    "org_id": org_id,
                    "event_type": "workflow.advance.requested",
                    "trace_id": trace_id,
                    "payload": {
                        "workflow_instance_id": instance_id,
                        "decided_level": level,
                        "approval_id": approval_id,
                    },
                }
            )
            if not result:
                result = workflow_orchestrator.advance_after_approval(
                    org_id=org_id,
                    instance=workflow_repo.get_instance(org_id, instance_id) or instance,
                    decided_level=level,
                    trace_id=trace_id,
                )
            audit_transition(
                org_id=org_id,
                actor_id=user_id,
                instance_id=instance_id,
                from_status=instance["status"],
                to_status=result.get("status", "executing"),
                detail={"approval_id": approval_id, "decision": "approved", "level": level},
            )
            self._sync_legacy(org_id, instance, result.get("status", "executing"))
            return {**row, "workflow_status": result.get("status")}
        target = apply_transition(current_status=instance["status"], target_status="rejected")
        with workflow_uow(org_id) as uow:
            uow.update_instance(instance_id, status=target, completed=True)
        emit_approval_rejected(org_id, approval_id, trace_id=trace_id)
        audit_transition(
            org_id=org_id,
            actor_id=user_id,
            instance_id=instance_id,
            from_status=instance["status"],
            to_status=target,
            detail={"approval_id": approval_id, "decision": "rejected"},
        )
        self._sync_legacy(org_id, instance, target)
        return row

    def _delegate(
        self,
        org_id: str,
        approval: dict,
        instance: dict,
        delegate_to: str | None,
        *,
        trace_id: str | None = None,
    ) -> dict:
        if not delegate_to:
            raise ValueError("delegate_to user id is required for delegated decision")
        full = approval_repo.get_approval(org_id, approval["id"]) or approval
        approval_id = full["id"]
        step_id = full.get("workflow_step_id")
        with workflow_uow(org_id) as uow:
            uow.decide_approval(approval_id, approver_user_id=delegate_to, decision="delegated", reason="delegated")
        tasks = task_repo.list_tasks(org_id, status="open", limit=50)
        for task in tasks:
            if task.get("workflow_instance_id") == instance["id"]:
                task_repo.assign_task(org_id, task["id"], delegate_to)
                break
        new_approval = approval_repo.create_approval(
            org_id=org_id,
            workflow_instance_id=instance["id"],
            workflow_step_id=step_id,
            requested_from_user_id=delegate_to,
            level=int(full.get("level") or 1),
        )
        from app.modules.workflows.events.workflow_events import emit_approval_requested

        emit_approval_requested(org_id, new_approval["id"], instance["id"], trace_id=trace_id)
        return {"status": "delegated", "approval_id": new_approval["id"]}

    def _expire(self, org_id: str, approval: dict, instance: dict, *, trace_id: str | None = None) -> dict:
        full = approval_repo.get_approval(org_id, approval["id"]) or approval
        with workflow_uow(org_id) as uow:
            uow.decide_approval(full["id"], approver_user_id="system", decision="expired", reason="sla_expired")
            uow.update_instance(instance["id"], status="timed_out")
        from app.modules.workflows.services.escalation_service import escalation_service

        escalation_service.escalate_instance(
            org_id=org_id,
            instance_id=instance["id"],
            escalation_type="sla_breach",
            step_id=full.get("workflow_step_id"),
            trace_id=trace_id,
        )
        return {"status": "expired"}

    def _sync_legacy(self, org_id: str, instance: dict, status: str) -> None:
        legacy_id = instance.get("legacy_workflow_id")
        if not legacy_id:
            return
        try:
            workflows_repo.add_timeline_step(
                org_id=org_id,
                workflow_id=legacy_id,
                step_type="workflow.approval.decided",
                state=status_to_legacy_state(status),
            )
        except Exception:
            pass


approval_service = ApprovalService()
