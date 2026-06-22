from app.services.canonicalization_service import normalize_connector_payload
from app.services.graph_extraction_service import extract_relationships_for_org
from app.services.langgraph_runner import run_langgraph_flow
from app.services.action_service import execute_action
from app.services.connectors import run_connector
from app.services.embedding_worker_service import ingest_document_for_embedding
from app.services.event_bus import event_bus
from app.services.logger import log_event
from app.services.principal_context import principal_from_envelope, principal_tuple
from app.services.repositories import agents_repo, audit_repo, memory_repo, sources_repo
from app.services.scheduler_service import run_scheduled_jobs_once


def _publish_child_event(envelope: dict, event_type: str, org_id: str, source: str, payload: dict) -> None:
    principal = principal_from_envelope(envelope)
    event_bus.publish(
        event_type=event_type,
        org_id=org_id,
        source=source,
        trace_id=str(envelope.get("trace_id", "")),
        payload=payload,
        principal=principal,
    )


def _consume_ingestion_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    if event_type != "source.sync.started":
        return
    source_id = str(payload.get("source_id", ""))
    source = sources_repo.get_source(org_id=org_id, source_id=source_id)
    if not source:
        return
    connector = str(source.get("source_type", ""))
    result = run_connector(org_id=org_id, connector=connector, mode="polling")
    status_event = "source.sync.completed" if result.status == "completed" else "source.sync.failed"
    _publish_child_event(
        envelope,
        event_type=status_event,
        org_id=org_id,
        source="worker.ingestion",
        payload={"source_id": source_id, "connector": connector, "detail": result.detail},
    )
    if result.status == "completed" and connector in {"docs", "erp", "crm", "ticketing"}:
        normalized = normalize_connector_payload(
            org_id=org_id,
            connector=connector,
            payload={"connector": connector, "amount": payload.get("amount"), "entity_name": payload.get("entity_name", connector)},
        )
        _publish_child_event(
            envelope,
            event_type="entity.resolved",
            org_id=org_id,
            source="worker.ingestion",
            payload={"connector": connector, "normalized": normalized},
        )
        ingest_document_for_embedding(
            org_id=org_id,
            source_id=source_id,
            title=f"{connector} sync payload",
            content=f"Connector {connector} sync completed with detail: {result.detail}",
            doc_type="connector_sync",
            permission_ref=sources_repo.get_source_ref(org_id=org_id, source_id=source_id),
        )


def _consume_chunk_processing_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    source_id = str(payload.get("source_id", ""))
    content = str(payload.get("content", "")).strip()
    if not source_id or not content:
        return
    ingest_document_for_embedding(
        org_id=org_id,
        source_id=source_id,
        title=str(payload.get("title", "chunk-processed")),
        content=content,
        doc_type=str(payload.get("doc_type", "connector_sync")),
        permission_ref=sources_repo.get_source_ref(org_id=org_id, source_id=source_id),
    )


def _consume_extract_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    connector = str(payload.get("connector", ""))
    normalize_connector_payload(org_id=org_id, connector=connector or "docs", payload=payload)
    _publish_child_event(
        envelope,
        event_type="graph.upsert.requested",
        org_id=org_id,
        source="worker.extract",
        payload={"connector": connector},
    )


def _consume_graph_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload") or {}
    if payload.get("entity_id") or payload.get("entity_type"):
        try:
            from app.modules.finance_os.graph.pipelines.graph_ingestion_pipeline import graph_ingestion_pipeline

            graph_ingestion_pipeline.run_from_event(envelope)
            return
        except Exception:
            pass
    extract_relationships_for_org(org_id=org_id)


def _consume_graph_ingestion(envelope: dict) -> None:
    """M28: incremental ERP event graph mutations."""
    event_type = str(envelope.get("event_type", ""))
    domain_events = {
        "erp.invoice.created",
        "invoice.created",
        "invoice.received",
        "erp.invoice.approved",
        "approval.requested",
        "approval.completed",
        "approval.rejected",
        "workflow.completed",
        "workflow.stage.completed",
        "workflow.failed",
        "sla.breached",
        "journal.posted",
        "erp.journal.posted",
        "payment.executed",
        "erp.payment.completed",
        "bank.transaction.imported",
        "bank.statement.imported",
        "reconciliation.completed",
        "reconciliation.adjustment.posted",
        "erp.gst.return.generated",
        "gst.transaction.recorded",
        "compliance.completed",
        "irn.generated",
        "invoice.anomaly_detected",
        "liquidity_alert.created",
        "workflow.bottleneck.detected",
    }
    if event_type not in domain_events:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from app.modules.finance_os.graph.pipelines.graph_ingestion_pipeline import graph_ingestion_pipeline

        graph_ingestion_pipeline.run_from_event(envelope)
    except Exception:
        pass
    if event_type == "workflow.bottleneck.detected":
        try:
            from app.modules.finance_os.graph.bridges.m26_bridge import annotate_workflow_bottleneck

            payload = envelope.get("payload") or {}
            wf_id = str(payload.get("workflow_instance_id") or payload.get("workflow_id") or "")
            bottleneck = str(payload.get("top_bottleneck") or payload.get("bottleneck_stage") or "")
            if wf_id and bottleneck:
                annotate_workflow_bottleneck(org_id, workflow_id=wf_id, bottleneck_stage=bottleneck)
        except Exception:
            pass


def _consume_agent_run_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    payload = envelope.get("payload", {})
    roles, attrs, _, _ = principal_tuple(envelope)
    flow = run_langgraph_flow(
        org_id=org_id,
        agent_type=str(payload.get("agent_type", "workflow_assistant")),
        trigger_type=str(payload.get("trigger_type", "event")),
        payload=payload if isinstance(payload, dict) else {},
        principal_roles=roles,
        principal_attrs=attrs,
    )
    row = agents_repo.create_run(
        org_id=org_id,
        agent_type=str(payload.get("agent_type", "workflow_assistant")),
        trigger_type=str(payload.get("trigger_type", "event")),
        status=flow.get("status", "failed"),
        outputs={"flow_result": flow, "payload": payload},
    )
    if str(payload.get("trigger_type", "")) == "workflow_step" and payload.get("step_id"):
        _resume_workflow_ai_step(org_id, payload, flow)
    if flow.get("status") == "pending_human_approval":
        _publish_child_event(
            envelope,
            event_type="agent.action.awaiting_approval",
            org_id=org_id,
            source="worker.agent",
            payload={
                "run_id": row.get("run_id"),
                "agent_type": payload.get("agent_type", "workflow_assistant"),
                "proposed_actions_count": len(flow.get("proposed_actions", [])),
            },
        )
    try:
        from app.modules.platform.governance.services.ai_trace_service import ai_trace_service

        summary = str(flow.get("summary") or flow.get("status", "completed"))[:2000]
        ai_trace_service.record_agent_decision(
            org_id,
            agent_run_id=str(row.get("run_id", row.get("id", ""))),
            workflow_id=str(payload.get("workflow_instance_id", "")) or None,
            prompt=str(payload.get("prompt", payload.get("agent_type", "workflow"))),
            summary=summary,
            confidence=float(flow.get("confidence", 0.5) or 0.5),
            decision={"status": flow.get("status"), "proposed_actions": len(flow.get("proposed_actions", []))},
        )
    except Exception:
        pass


def _consume_memory_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    if payload.get("memory_record_id") and not payload.get("content") and not payload.get("subject_ref"):
        return
    try:
        from app.modules.finance_os.memory.pipelines.memory_ingestion_pipeline import memory_ingestion_pipeline

        memory_ingestion_pipeline.run_from_event(envelope)
        return
    except Exception:
        pass
    subject_ref = str(payload.get("subject_ref", "")).strip()
    if not subject_ref:
        return
    memory_repo.create_memory(
        org_id=org_id,
        memory_type=str(payload.get("memory_type", "workflow")),
        subject_ref=subject_ref,
        payload_jsonb={"event_type": envelope.get("event_type"), "payload": payload},
        relevance_score=float(payload.get("relevance_score", 0.75)),
    )


def _consume_agent_action_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    tool = str(payload.get("tool", ""))
    method = str(payload.get("method", ""))
    params = payload.get("params", {})
    if not tool or not method or not isinstance(params, dict):
        return
    roles, attrs, human_approved, actor_id = principal_tuple(envelope)
    execute_action(
        org_id=org_id,
        actor_id=actor_id,
        tool=tool,
        method=method,
        params=params,
        attrs=attrs,
        roles=roles,
        human_approved=human_approved,
    )


def _consume_consolidation_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import materialize_from_envelope

        materialize_from_envelope(envelope)
    except Exception:
        pass
    if event_type == "intercompany.mismatch.detected":
        log_event("consolidation.ic_mismatch", org_id=org_id, payload=envelope.get("payload"))


def _consume_policy_events(envelope: dict) -> None:
    """Supplementary risk context for M34 policy events (debounced audit enrichment)."""
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id or not event_type.startswith("policy."):
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    try:
        from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import materialize_from_envelope

        materialize_from_envelope(envelope)
    except Exception:
        pass
    if event_type in {"policy.risk.detected", "policy.denied", "policy.override.required"}:
        log_event(
            "policy.event.consumed",
            org_id=org_id,
            event_type=event_type,
            action=str(payload.get("action") or ""),
        )


def _consume_audit_event(envelope: dict) -> None:
    from app.modules.platform.governance.services.audit_service import audit_service

    audit_service.persist_from_event_envelope(envelope)
    _consume_governance_event(envelope)


def _consume_governance_event(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    if event_type.startswith("policy."):
        _consume_policy_events(envelope)
    if event_type.startswith(("consolidation.", "intercompany.", "elimination.")) or event_type == "entity.closed":
        _consume_consolidation_events(envelope)
    if event_type == "policy.violation.detected":
        from app.modules.platform.governance.services.realtime_bridge import governance_realtime_bridge

        governance_realtime_bridge.push_violation(org_id, envelope)
    elif event_type == "compliance.alert.generated":
        from app.modules.platform.governance.services.realtime_bridge import governance_realtime_bridge

        governance_realtime_bridge.push_compliance_alert(org_id, envelope)


def _consume_notification_event(envelope: dict, *, queue: str = "") -> None:
    from app.modules.platform.notifications.workers.notification_worker import process_notification_event

    event_type = str(envelope.get("event_type", ""))
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    if event_type == "notification.deliver":
        process_notification_event(envelope, queue=queue or None, claim_token=envelope.get("_claim_token"))
        return
    if payload.get("tool"):
        org_id = str(envelope.get("org_id", ""))
        roles, attrs, human_approved, actor_id = principal_tuple(envelope)
        execute_action(
            org_id=org_id,
            actor_id=actor_id,
            tool=str(payload.get("tool", "slack")),
            method=str(payload.get("method", "postMessage")),
            params=payload.get("params", {}),
            attrs=attrs,
            roles=roles,
            human_approved=human_approved,
        )
        return
    process_notification_event(envelope)


def _should_route_domain_notification(envelope: dict, queue: str) -> bool:
    if "notifications." in queue:
        return False
    event_type = str(envelope.get("event_type", ""))
    if event_type.startswith("notification."):
        return False
    return True


def _consume_agent_plan_event(envelope: dict) -> None:
    payload = envelope.get("payload", {})
    org_id = str(envelope.get("org_id", ""))
    run_id = str(payload.get("run_id", "")).strip()
    if run_id:
        run = agents_repo.get_run(org_id=org_id, run_id=run_id)
        if not run or str(run.get("status", "")).lower() != "approved":
            return
    roles, attrs, _, actor_id = principal_tuple(envelope)
    for action in payload.get("actions", []):
        if not isinstance(action, dict):
            continue
        execute_action(
            org_id=org_id,
            actor_id=actor_id,
            tool=str(action.get("tool", "")),
            method=str(action.get("method", "")),
            params=action.get("params", {}),
            attrs=attrs,
            roles=roles,
            human_approved=True,
        )


def _consume_retry_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    run_scheduled_jobs_once(org_id=org_id)


def _consume_workflow_execution_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    if event_type in {"erp.invoice.created", "invoice.created"}:
        from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

        handle_entity_created(org_id=org_id, payload=payload, trace_id=str(envelope.get("trace_id", "")))
        return
    if event_type in {"workflow.retry.scheduled", "workflow.step.completed"}:
        from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator

        instance_id = str(payload.get("workflow_instance_id", ""))
        step_id = str(payload.get("step_id", ""))
        if step_id and event_type == "workflow.step.completed":
            from app.modules.workflows.services.step_service import step_service

            step_service.complete_step(
                org_id=org_id,
                step_id=step_id,
                actor_id="system",
                result=str(payload.get("status", "completed")),
                output=payload.get("output") if isinstance(payload.get("output"), dict) else {},
                trace_id=str(envelope.get("trace_id", "")) or None,
            )
            return
        if instance_id:
            workflow_orchestrator.run_from_step(org_id=org_id, instance_id=instance_id)


def _consume_workflow_sla_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    from app.modules.workflows.workers.sla_worker import run_sla_checks

    run_sla_checks(org_id, trace_id=str(envelope.get("trace_id", "")))


def _consume_workflow_approval_event(envelope: dict) -> dict | None:
    org_id = str(envelope.get("org_id", ""))
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    event_type = str(envelope.get("event_type", ""))
    if event_type not in {"workflow.advance.requested", "approval.completed"}:
        return None
    instance_id = str(payload.get("workflow_instance_id", ""))
    if not instance_id:
        return None
    from app.modules.workflows.repositories import workflow_repo
    from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator

    instance = workflow_repo.get_instance(org_id, instance_id)
    if not instance:
        return None
    decided_level = int(payload.get("decided_level") or 0)
    return workflow_orchestrator.advance_after_approval(
        org_id=org_id,
        instance=instance,
        decided_level=decided_level,
        trace_id=str(envelope.get("trace_id", "")) or None,
    )


def _resume_workflow_ai_step(org_id: str, payload: dict, flow: dict) -> None:
    step_id = str(payload.get("step_id", "")).strip()
    if not step_id:
        return
    from app.modules.workflows.services.step_service import step_service

    status = str(flow.get("status", "completed")).lower()
    result = "completed" if status not in {"failed", "error"} else "failed"
    output = flow.get("outputs") or flow.get("flow_result") or {}
    step_service.complete_step(
        org_id=org_id,
        step_id=step_id,
        actor_id="agent:workflow_assistant",
        result=result,
        output=output if isinstance(output, dict) else {"result": output},
        trace_id=str(payload.get("trace_id", "")) or None,
    )


def _consume_workflow_escalation_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    from app.modules.workflows.workers.escalation_worker import run_escalation_checks

    run_escalation_checks(org_id, trace_id=str(envelope.get("trace_id", "")))


def _emit_ap_invoice_due_events(org_id: str) -> None:
    from datetime import date

    from app.modules.erp.accounts_payable.events.ap_events import emit_invoice_due
    from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

    today = date.today().isoformat()
    for inv in invoice_repository.list_outstanding(org_id):
        due = str(inv.get("due_date") or "")[:10]
        if due and due <= today:
            emit_invoice_due(org_id, invoice_id=str(inv.get("id")), due_date=due)


def _consume_notification_digest_event(envelope: dict) -> None:
    from app.modules.platform.notifications.workers.digest_worker import run_digest_batch_for_org

    org_id = str(envelope.get("org_id", ""))
    run_digest_batch_for_org(org_id)


def _consume_scheduler_event(envelope: dict) -> None:
    org_id = str(envelope.get("org_id", ""))
    event_type = str(envelope.get("event_type", ""))
    if event_type == "scheduler.notifications.digest":
        _consume_notification_digest_event(envelope)
        return
    if event_type in {"scheduler.sla.scan", "scheduler.tick"}:
        _consume_workflow_sla_event(envelope)
        if event_type == "scheduler.tick":
            try:
                from app.modules.platform.documents.services.retention_service import document_retention_service

                document_retention_service.enforce_retention(org_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("scheduler.tick retention failed org=%s: %s", org_id, exc)
            if org_id:
                try:
                    from app.modules.erp.journals.services.recurring_journal_service import recurring_journal_service

                    recurring_journal_service.run_due(org_id)
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning("scheduler.tick recurring journals failed org=%s: %s", org_id, exc)
                try:
                    from app.modules.erp.journals.services.accrual_service import accrual_service

                    accrual_service.process_due_reversals(org_id)
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning("scheduler.tick accrual reversals failed org=%s: %s", org_id, exc)
                try:
                    _emit_ap_invoice_due_events(org_id)
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning("scheduler.tick AP due invoices failed org=%s: %s", org_id, exc)
                try:
                    from app.modules.erp.accounts_receivable.services.dunning_service import dunning_service

                    dunning_service.process_due_invoices(org_id)
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning("scheduler.tick AR dunning failed org=%s: %s", org_id, exc)
                try:
                    from app.modules.erp.assets.services.depreciation_service import depreciation_service

                    depreciation_service.run_due(org_id)
                except Exception as exc:
                    import logging

                    logging.getLogger(__name__).warning("scheduler.tick asset depreciation failed org=%s: %s", org_id, exc)
    elif event_type in {"scheduler.escalation.scan"}:
        _consume_workflow_escalation_event(envelope)
    elif event_type in {"scheduler.reconciliation.daily"}:
        from app.modules.platform.events.workers.reconciliation_worker import process_reconciliation_event

        process_reconciliation_event(org_id, envelope)
    elif event_type in {"scheduler.compliance.daily"}:
        if org_id:
            try:
                from app.modules.erp.compliance.services.compliance_scheduler_service import compliance_scheduler_service

                compliance_scheduler_service.run_daily(org_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("scheduler.compliance.daily failed org=%s: %s", org_id, exc)
    elif event_type in {"scheduler.treasury.daily"}:
        if org_id:
            try:
                from app.modules.erp.treasury.jobs.treasury_daily_job import run_treasury_daily

                run_treasury_daily(org_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("scheduler.treasury.daily failed org=%s: %s", org_id, exc)
    elif event_type in {"scheduler.reports.daily"}:
        if org_id:
            try:
                from app.modules.erp.reporting.pipelines.report_refresh_pipeline import run_refresh as run_report_refresh

                run_report_refresh(org_id, trace_id=str(envelope.get("trace_id") or ""))
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("scheduler.reports.daily failed org=%s: %s", org_id, exc)
    elif event_type in {"scheduler.analytics.daily"}:
        if org_id:
            try:
                from app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline import run_refresh as run_analytics_refresh

                run_analytics_refresh(org_id, trace_id=str(envelope.get("trace_id") or ""))
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("scheduler.analytics.daily failed org=%s: %s", org_id, exc)


def _consume_ai_queue_event(envelope: dict) -> None:
    from app.modules.platform.events.workers.ai_worker import process_ai_event

    process_ai_event(envelope)


def _consume_ocr_event(envelope: dict) -> None:
    from app.modules.platform.events.workers.ocr_worker import process_ocr_event

    process_ocr_event(envelope)


def _consume_integration_event(envelope: dict) -> None:
    from app.modules.platform.events.workers.webhook_worker import process_integration_event

    process_integration_event(envelope)


def _consume_reports_event(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    try:
        from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository

        if not reporting_schema_repository.schema_ready():
            return
        if event_type == "reports.generate.requested":
            run_id = str(payload.get("run_id") or "")
            if run_id:
                from app.modules.erp.reporting.pipelines.export_pipeline import run_export

                run_export(org_id, run_id=run_id)
            return
        if event_type == "reports.refresh.requested":
            from app.modules.erp.reporting.pipelines.report_refresh_pipeline import run_refresh

            run_refresh(org_id, fiscal_period_id=payload.get("fiscal_period_id"), trace_id=str(envelope.get("trace_id") or ""))
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("reports consumer failed org=%s: %s", org_id, exc)


def _consume_document_intelligence_event(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    if event_type not in {
        "invoice.created",
        "erp.invoice.created",
        "vendor.onboarded",
        "workflow.started",
        "erp.payment.completed",
        "journal.posted",
        "approval.requested",
        "approval.completed",
    }:
        return
    document_ids: list[str] = []
    primary_document_id = str(payload.get("document_id", "")).strip()
    if primary_document_id:
        document_ids.append(primary_document_id)
    if isinstance(payload.get("document_ids"), list):
        document_ids.extend([str(d).strip() for d in payload.get("document_ids", []) if str(d).strip()])
    if not document_ids:
        return
    from app.modules.platform.documents.services.evidence_service import evidence_service

    if event_type in {"invoice.created", "erp.invoice.created"} and payload.get("invoice_id"):
        for did in document_ids:
            evidence_service.link(
                org_id,
                document_id=did,
                entity_type="invoice",
                entity_id=str(payload.get("invoice_id")),
                workflow_id=str(payload.get("workflow_id", "")) or None,
                metadata={"linked_by": "event_consumer", "event_type": event_type},
            )
    elif event_type == "vendor.onboarded" and payload.get("vendor_id"):
        for did in document_ids:
            evidence_service.link(
                org_id,
                document_id=did,
                entity_type="vendor",
                entity_id=str(payload.get("vendor_id")),
                metadata={"linked_by": "event_consumer", "event_type": event_type},
            )


def _consume_coa_events(envelope: dict) -> None:
    """
    Module 8 consumers (best-effort) for events that should influence COA intelligence/guards.
    """
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    # vendor.created -> placeholder for vendor-account mapper (future)
    if event_type in {"vendor.created", "erp.vendor.created"}:
        return

    # invoice.extracted -> can be used for AI suggestions / mapping enrichment (future)
    if event_type in {"invoice.extracted"}:
        return

    if event_type in {"journal.posted", "erp.journal.posted"}:
        journal_id = str(payload.get("journal_id") or "").strip()
        if journal_id:
            try:
                from app.modules.erp.coa.repositories.account_usage_repository import account_usage_repository
                from app.modules.erp.journals.repositories.journal_line_repository import journal_line_repository

                lines = journal_line_repository.list_by_journal(org_id, journal_id=journal_id)
                for line in lines:
                    aid = str(line.get("account_id") or "")
                    if not aid:
                        continue
                    usage = account_usage_repository.get_or_default(org_id, account_id=aid)
                    account_usage_repository.upsert(
                        org_id,
                        account_id=aid,
                        has_balance=bool(usage.get("has_balance")),
                        used_in_journals=True,
                    )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("journal.posted COA usage update failed org=%s: %s", org_id, exc)
        return

def _consume_document_security_event(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    if event_type != "document.malware_scan.requested":
        return
    org_id = str(envelope.get("org_id", ""))
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    document_id = str(payload.get("document_id") or envelope.get("entity_id") or "").strip()
    if not org_id or not document_id:
        return
    from app.modules.platform.documents.workers.malware_scan_worker import process_malware_scan_job

    process_malware_scan_job(org_id, document_id=document_id)

def _push_document_realtime(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    if not (
        event_type.startswith("document.")
        or event_type.startswith("ocr.")
        or event_type.startswith("duplicate.")
    ):
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    document_id = str(payload.get("document_id") or envelope.get("entity_id") or "").strip()
    if not document_id:
        return
    try:
        from app.modules.platform.documents.services.realtime_documents_service import realtime_documents_service
        from app.modules.platform.documents.repositories.document_repository import document_repository
        from app.modules.platform.documents.services.storage_service import storage_service

        # Enrich realtime payloads with preview URLs for Action Center/workflow UIs.
        try:
            doc = document_repository.get_document(org_id, document_id=document_id)
            previews = storage_service.preview_urls(
                str(doc.get("storage_path", "")),
                mime_type=str(doc.get("mime_type", "")),
                expires_in_seconds=900,
            )
            payload = {**payload, "previews": previews}
        except Exception:
            pass

        realtime_documents_service.push_document_event(
            org_id,
            event_type=event_type,
            document_id=document_id,
            payload=payload,
        )
    except Exception:
        pass


def _consume_m25_invoice_pipeline(envelope: dict) -> None:
    """Single M25 entry: OCR/extraction events trigger invoice intelligence pipeline."""
    event_type = str(envelope.get("event_type", ""))
    if event_type not in {"ocr.completed", "document.extracted", "invoice.ai.reviewed"}:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}

    if event_type == "invoice.ai.reviewed":
        if str(review.get("status", "")).lower() != "ocr_completed":
            return

    document_id = str(
        payload.get("document_id")
        or payload.get("invoice_id")
        or review.get("document_id")
        or envelope.get("entity_id")
        or ""
    ).strip()
    if not document_id:
        return

    try:
        from app.modules.platform.documents.repositories.document_repository import document_repository

        doc = document_repository.get_document(org_id, document_id) or {}
        doc_type = str(doc.get("document_type") or "").lower()
        if doc_type in {"receipt", "expense_receipt"}:
            return
    except Exception:
        pass

    try:
        from app.modules.finance_os.invoice_ai.pipelines.invoice_pipeline import invoice_pipeline

        invoice_pipeline.run(org_id, document_id=document_id)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "M25 invoice pipeline failed org=%s doc=%s: %s", org_id, document_id, exc
        )


def _consume_invoice_predicted(envelope: dict) -> None:
    """AP auto-draft when M25 confidence band allows and no hard blocks."""
    event_type = str(envelope.get("event_type", ""))
    if event_type != "invoice.predicted":
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    if not payload.get("auto_draft_eligible"):
        return
    extraction_id = str(payload.get("extraction_id") or "").strip()
    document_id = str(payload.get("document_id") or "").strip()
    if not extraction_id:
        return

    try:
        from app.modules.erp.accounts_payable.services.ai_invoice_service import ai_invoice_service

        ai_invoice_service.create_from_m25(
            org_id,
            extraction_id=extraction_id,
            source_document_id=document_id or None,
            created_by="ai.invoice",
            pipeline_result=payload,
        )
    except ValueError:
        return
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "AP draft from invoice.predicted failed org=%s extraction=%s: %s",
            org_id,
            extraction_id,
            exc,
        )


def _consume_agents_trigger(envelope: dict) -> None:
    """M29: auto-trigger Finance OS domain agents from ERP/AI events."""
    from app.modules.finance_os.agents.orchestrator.task_router import EVENT_AGENT_MAP

    event_type = str(envelope.get("event_type", ""))
    if event_type not in EVENT_AGENT_MAP:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline
        from app.modules.finance_os.agents.repositories.execution_repository import execution_repository

        if not execution_repository.schema_ready():
            return
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
        payload = {**payload, "source_event_type": event_type, "event_type": event_type}
        entity_id = str(payload.get("entity_id") or payload.get("invoice_id") or payload.get("object_id") or "")
        if entity_id:
            payload.setdefault("entity_id", entity_id)
        agent_orchestration_pipeline.run(
            org_id,
            EVENT_AGENT_MAP[event_type],
            "event",
            payload,
            trace_id=str(envelope.get("trace_id") or ""),
            source_event_type=event_type,
        )
    except Exception:
        pass


def _consume_forecasting_refresh(envelope: dict) -> None:
    """M30: refresh forecasts on posted/reconciled events (debounced per org)."""
    event_type = str(envelope.get("event_type", ""))
    trigger_events = {
        "journal.posted",
        "erp.journal.posted",
        "payment.received",
        "customer.payment.received",
        "reconciliation.completed",
        "cash.position.updated",
        "expense.claim.approved",
        "scheduler.treasury.daily",
    }
    if event_type not in trigger_events:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from time import time

        from app.modules.finance_os.forecasting.repositories.forecast_repository import forecast_repository
        from app.modules.finance_os.forecasting.pipelines.forecast_refresh_pipeline import run_refresh

        if not forecast_repository.schema_ready():
            return
        now = time()
        # module-local debounce map
        key = f"m30:{org_id}"
        last = getattr(_consume_forecasting_refresh, "_last", {})
        last_ts = float(last.get(key) or 0.0)
        if now - last_ts < 20.0:
            setattr(_consume_forecasting_refresh, "_last", last)
            return
        last[key] = now
        setattr(_consume_forecasting_refresh, "_last", last)
        run_refresh(org_id, trace_id=str(envelope.get("trace_id") or ""))
    except Exception:
        pass


def _consume_reporting_refresh(envelope: dict) -> None:
    """M31: refresh reporting MVs on domain events (debounced per org)."""
    event_type = str(envelope.get("event_type", ""))
    trigger_events = {
        "journal.posted",
        "erp.journal.posted",
        "invoice.approved",
        "erp.invoice.approved",
        "payment.executed",
        "payment.received",
        "customer.payment.received",
        "reconciliation.completed",
        "erp.fiscal_period.closed",
        "erp.period.closed",
        "forecast.generated",
        "scheduler.reports.daily",
    }
    if event_type not in trigger_events:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from time import time

        from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository
        from app.modules.erp.reporting.pipelines.report_refresh_pipeline import run_refresh

        if not reporting_schema_repository.schema_ready():
            return
        now = time()
        key = f"m31:{org_id}"
        last = getattr(_consume_reporting_refresh, "_last", {})
        last_ts = float(last.get(key) or 0.0)
        if now - last_ts < 30.0:
            setattr(_consume_reporting_refresh, "_last", last)
            return
        last[key] = now
        setattr(_consume_reporting_refresh, "_last", last)
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
        run_refresh(org_id, fiscal_period_id=payload.get("fiscal_period_id"), trace_id=str(envelope.get("trace_id") or ""))
    except Exception:
        pass


def _consume_audit_explorer_materialize(envelope: dict) -> None:
    """M33: materialize finance_audit timelines from domain and audit events (debounced)."""
    event_type = str(envelope.get("event_type", ""))
    from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import (
        MATERIALIZE_EVENT_TYPES,
        materialize_from_envelope,
    )

    if event_type not in MATERIALIZE_EVENT_TYPES:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from time import time

        from app.modules.finance_os.audit_explorer.repositories.schema_repository import audit_schema_repository

        if not audit_schema_repository.schema_ready():
            return
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
        object_id = str(
            payload.get("object_id")
            or payload.get("entity_id")
            or payload.get("execution_id")
            or payload.get("workflow_instance_id")
            or ""
        )
        now = time()
        key = f"m33:{org_id}:{object_id or event_type}"
        last = getattr(_consume_audit_explorer_materialize, "_last", {})
        last_ts = float(last.get(key) or 0.0)
        if now - last_ts < 5.0 and event_type != "audit.log.created":
            return
        last[key] = now
        setattr(_consume_audit_explorer_materialize, "_last", last)
        materialize_from_envelope(envelope)
    except Exception:
        pass


def _consume_analytics_refresh(envelope: dict) -> None:
    """M32: refresh KPI snapshots on report/forecast/close events (debounced per org)."""
    event_type = str(envelope.get("event_type", ""))
    trigger_events = {
        "report.generated",
        "report.snapshot.created",
        "forecast.generated",
        "forecast.accuracy.calculated",
        "erp.fiscal_period.closed",
        "erp.period.closed",
        "payment.executed",
        "reconciliation.completed",
        "scheduler.analytics.daily",
    }
    if event_type not in trigger_events:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from time import time

        from app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline import run_refresh
        from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository

        if not analytics_schema_repository.schema_ready():
            return
        now = time()
        key = f"m32:{org_id}"
        last = getattr(_consume_analytics_refresh, "_last", {})
        last_ts = float(last.get(key) or 0.0)
        if now - last_ts < 30.0:
            setattr(_consume_analytics_refresh, "_last", last)
            return
        last[key] = now
        setattr(_consume_analytics_refresh, "_last", last)
        payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
        run_refresh(org_id, fiscal_period_id=payload.get("fiscal_period_id"), trace_id=str(envelope.get("trace_id") or ""))
    except Exception:
        pass


def _consume_memory_ingestion(envelope: dict) -> None:
    """M27: ingest meaningful domain events into finance_os memory."""
    event_type = str(envelope.get("event_type", ""))
    domain_events = {
        "payment.executed",
        "erp.payment.completed",
        "approval.completed",
        "approval.rejected",
        "workflow.approved",
        "workflow.intelligence.completed",
        "invoice.predicted",
        "invoice.duplicate_detected",
        "invoice.anomaly_detected",
        "erp.invoice.approved",
        "journal.posted",
        "erp.journal.posted",
        "liquidity_alert.created",
        "cash.forecast.updated",
        "treasury.risk.detected",
        "compliance.alert.generated",
        "compliance.alert",
        "gst.mismatch.detected",
        "reconciliation.completed",
        "reconciliation.adjustment.posted",
        "decision.recorded",
    }
    if event_type not in domain_events:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    try:
        from app.modules.finance_os.memory.pipelines.memory_ingestion_pipeline import memory_ingestion_pipeline

        memory_ingestion_pipeline.run_from_event(envelope)
    except Exception:
        pass


def _consume_workflow_intelligence(envelope: dict) -> None:
    """M26: workflow intelligence pipeline on lifecycle events."""
    event_type = str(envelope.get("event_type", ""))
    trigger_events = {
        "workflow.completed",
        "workflow.failed",
        "workflow.stage.completed",
        "approval.completed",
        "sla.breached",
    }
    if event_type not in trigger_events:
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    instance_id = str(payload.get("workflow_instance_id") or "").strip()
    if not instance_id and event_type in {"approval.completed", "approval.rejected"}:
        approval_id = str(payload.get("approval_id") or "").strip()
        if approval_id:
            try:
                from app.modules.workflows.repositories import approval_repo

                appr = approval_repo.get_approval(org_id, approval_id) or {}
                instance_id = str(appr.get("workflow_instance_id") or "")
            except Exception:
                instance_id = ""
    if not instance_id:
        return
    try:
        from app.modules.finance_os.workflow_intelligence.pipelines.workflow_intelligence_pipeline import (
            workflow_intelligence_pipeline,
        )

        workflow_intelligence_pipeline.run(
            org_id,
            workflow_instance_id=instance_id,
            trace_id=str(envelope.get("trace_id") or ""),
        )
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "M26 workflow intelligence failed org=%s instance=%s: %s", org_id, instance_id, exc
        )


def _consume_invoice_ai_reviewed(envelope: dict) -> None:
    """Deprecated alias — pipeline handled by _consume_m25_invoice_pipeline."""
    return


def _consume_workflow_system_task_gl_post(envelope: dict) -> None:
    """
    Wire workflow system task -> GL posting.
    Workflow definitions can include a system_task with step_key == 'gl.post'
    and instance.metadata.gl_post_request holding the posting payload.
    """
    event_type = str(envelope.get("event_type", ""))
    if event_type != "workflow.step.system_task":
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    step_key = str(payload.get("step_key") or "")
    if step_key not in {"gl.post", "journal.post"}:
        return
    instance_id = str(payload.get("workflow_instance_id") or "").strip()
    if not instance_id:
        return
    try:
        from app.modules.workflows.repositories import workflow_repo

        instance = workflow_repo.get_instance(org_id, instance_id) or {}
    except Exception:
        return
    metadata = instance.get("metadata") if isinstance(instance.get("metadata"), dict) else {}
    journal_id = str(metadata.get("journal_id") or "").strip()
    posted_by = str(instance.get("owner_user_id") or "workflow")
    try:
        if journal_id:
            from app.modules.erp.journals.ai.confidence_engine import requires_finance_review
            from app.modules.erp.journals.services.approval_service import approval_service
            from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
            from app.modules.erp.journals.repositories.journal_repository import journal_repository

            journal = journal_repository.get(org_id, journal_id=journal_id) or {}
            status = str(journal.get("journal_status") or "")
            approver = str(metadata.get("approver_user_id") or posted_by)
            if requires_finance_review(journal.get("ai_confidence") if isinstance(journal.get("ai_confidence"), dict) else {}):
                return
            if status in {"draft", "pending_approval"}:
                approval_service.approve(org_id, journal_id=journal_id, approver_id=approver)
            result = posting_orchestrator.post_journal(org_id, journal_id=journal_id, posted_by=posted_by)
            batch_id = result.get("ledger_batch_id")
            _publish_child_event(
                envelope,
                event_type="journal.posted",
                org_id=org_id,
                source="workflow.journal_post",
                payload={"journal_id": journal_id, "batch_id": batch_id, "workflow_instance_id": instance_id},
            )
            return

        gl_req = metadata.get("gl_post_request") if isinstance(metadata.get("gl_post_request"), dict) else None
        if not gl_req:
            return
        from app.modules.erp.gl.services.posting_service import posting_service

        result = posting_service.post(
            org_id,
            posted_by=posted_by,
            posting_date=str(gl_req.get("posting_date") or metadata.get("posting_date") or "")[:10],
            company_id=gl_req.get("company_id"),
            lines=gl_req.get("lines") or [],
        )
        batch_id = ((result.get("batch") or {}).get("id")) if isinstance(result, dict) else None
        if batch_id:
            _publish_child_event(
                envelope,
                event_type="erp.journal.posted",
                org_id=org_id,
                source="workflow.gl_post",
                payload={"batch_id": batch_id, "workflow_instance_id": instance_id},
            )
    except Exception:
        return


def _resolve_workflow_domain_context(org_id: str, payload: dict) -> dict:
    """Merge workflow instance metadata into payload for domain consumers."""
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    merged = {**metadata, **{k: v for k, v in payload.items() if v is not None}}
    instance_id = str(payload.get("workflow_instance_id") or "").strip()
    approval_id = str(payload.get("approval_id") or "").strip()
    try:
        from app.modules.workflows.repositories import workflow_repo
        from app.modules.workflows.repositories.approval_repository import approval_repo

        if not instance_id and approval_id:
            approval = approval_repo.get_approval(org_id, approval_id) or {}
            instance_id = str(approval.get("workflow_instance_id") or "").strip()
            merged.setdefault("approver_user_id", approval.get("decided_by") or approval.get("requested_from_user_id"))
        if instance_id:
            instance = workflow_repo.get_instance(org_id, instance_id) or {}
            inst_meta = instance.get("metadata") if isinstance(instance.get("metadata"), dict) else {}
            merged = {**inst_meta, **merged}
            merged.setdefault("entity_type", instance.get("entity_type"))
            merged.setdefault("entity_id", instance.get("entity_id"))
            merged.setdefault("workflow_type", instance.get("workflow_type"))
            merged.setdefault("workflow_instance_id", instance_id)
    except Exception:
        pass
    return merged


def _handle_ar_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    """Route completed AR workflows to domain services. Returns True if handled."""
    import logging

    log = logging.getLogger(__name__)
    ctx = _resolve_workflow_domain_context(org_id, payload)
    instance_id = str(ctx.get("workflow_instance_id") or "").strip()
    if event_type == "approval.completed" and instance_id:
        try:
            from app.modules.workflows.repositories import workflow_repo

            instance = workflow_repo.get_instance(org_id, instance_id) or {}
            if str(instance.get("status") or "") != "completed":
                return False
        except Exception:
            return False
    elif event_type not in {"", "workflow.completed", "workflow.approved"}:
        return False

    entity_type = str(ctx.get("entity_type") or "").strip()
    workflow_type = str(ctx.get("workflow_type") or "").strip()
    approver = str(
        ctx.get("approver_user_id") or ctx.get("approved_by") or ctx.get("started_by") or "workflow"
    ).strip()

    if entity_type == "customer_credit" or workflow_type == "AR_CREDIT_LIMIT_APPROVAL":
        customer_id = str(ctx.get("customer_id") or ctx.get("entity_id") or "").strip()
        new_limit = ctx.get("new_credit_limit")
        if customer_id and new_limit is not None:
            try:
                from app.modules.erp.accounts_receivable.services.customer_service import customer_service

                customer_service.apply_credit_limit_approval(
                    org_id,
                    customer_id=customer_id,
                    new_credit_limit=float(new_limit),
                    approver_id=approver,
                )
                return True
            except Exception as exc:
                log.warning("AR credit limit approval failed org=%s customer=%s: %s", org_id, customer_id, exc)
        return False

    if entity_type == "ar_writeoff" or workflow_type == "AR_WRITE_OFF_APPROVAL":
        invoice_id = str(ctx.get("ar_invoice_id") or ctx.get("entity_id") or "").strip()
        bad_debt_account_id = str(ctx.get("bad_debt_account_id") or "").strip() or None
        auto_post = ctx.get("auto_post")
        if invoice_id:
            try:
                from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
                from app.modules.erp.accounts_receivable.services.sales_invoice_service import sales_invoice_service

                invoice = ar_invoice_repository.get(org_id, invoice_id=invoice_id) or {}
                meta = invoice.get("metadata") if isinstance(invoice.get("metadata"), dict) else {}
                meta["writeoff_workflow_approved"] = True
                meta.pop("writeoff_pending", None)
                ar_invoice_repository.update_metadata(org_id, invoice_id=invoice_id, metadata=meta)
                sales_invoice_service.execute_write_off(
                    org_id,
                    invoice_id=invoice_id,
                    approver_id=approver,
                    bad_debt_account_id=bad_debt_account_id,
                    auto_post=bool(auto_post) if auto_post is not None else None,
                    skip_workflow_check=True,
                )
                return True
            except Exception as exc:
                log.warning("AR write-off from workflow failed org=%s invoice=%s: %s", org_id, invoice_id, exc)
        return False

    ar_invoice_id = str(ctx.get("ar_invoice_id") or "").strip()
    if not ar_invoice_id and entity_type == "sales_invoice":
        ar_invoice_id = str(ctx.get("entity_id") or "").strip()
    if ar_invoice_id and not ctx.get("bad_debt_account_id"):
        try:
            from app.modules.erp.accounts_receivable.services.sales_invoice_service import sales_invoice_service

            sales_invoice_service.issue_invoice(
                org_id, invoice_id=ar_invoice_id, issued_by=approver, auto_post=True, force_credit_approval=True
            )
            return True
        except Exception as exc:
            log.warning("AR invoice issue from workflow failed org=%s invoice=%s: %s", org_id, ar_invoice_id, exc)
    return False


def _handle_treasury_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    import logging

    log = logging.getLogger(__name__)
    ctx = _resolve_workflow_domain_context(org_id, payload)
    instance_id = str(ctx.get("workflow_instance_id") or "").strip()
    if event_type == "approval.completed" and instance_id:
        try:
            from app.modules.workflows.repositories import workflow_repo

            instance = workflow_repo.get_instance(org_id, instance_id) or {}
            if str(instance.get("status") or "") != "completed":
                return False
        except Exception:
            return False
    elif event_type not in {"", "workflow.completed", "workflow.approved"}:
        return False

    entity_type = str(ctx.get("entity_type") or "").strip()
    workflow_type = str(ctx.get("workflow_type") or "").strip()
    if entity_type != "treasury_payment" and workflow_type != "TREASURY_PAYMENT_APPROVAL":
        return False

    payment_request_id = str(ctx.get("payment_request_id") or ctx.get("entity_id") or "").strip()
    if not payment_request_id:
        return False
    approver = str(ctx.get("approver_user_id") or ctx.get("approved_by") or "workflow")
    try:
        from app.modules.erp.treasury.services.payment_service import treasury_payment_service

        treasury_payment_service.mark_workflow_approved(
            org_id, payment_request_id=payment_request_id, approver_id=approver
        )
        return True
    except Exception as exc:
        log.warning("Treasury payment workflow failed org=%s req=%s: %s", org_id, payment_request_id, exc)
    return False


def _consume_treasury_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"payment.scheduled", "erp.payment.scheduled"}:
        ap_payment_id = str(payload.get("payment_id") or payload.get("ap_payment_id") or payload.get("entity_id") or "").strip()
        if ap_payment_id:
            try:
                from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository
                from app.modules.erp.treasury.services.payment_service import treasury_payment_service

                payment = payment_repository.get(org_id, payment_id=ap_payment_id) or {}
                vendor_bank_account_id = payload.get("vendor_bank_account_id")
                if not vendor_bank_account_id:
                    pmeta = payment.get("metadata") if isinstance(payment.get("metadata"), dict) else {}
                    vendor_bank_account_id = pmeta.get("vendor_bank_account_id")
                treasury_payment_service.create_from_ap_scheduled(
                    org_id,
                    ap_payment_id=ap_payment_id,
                    bank_account_id=str(payload.get("bank_account_id") or payment.get("bank_account_id") or ""),
                    amount=float(payload.get("amount") or payment.get("amount") or 0),
                    vendor_id=str(payload.get("vendor_id") or payment.get("vendor_id") or ""),
                    scheduled_date=str(payload.get("payment_date") or payment.get("payment_date") or "")[:10],
                    created_by=str(payload.get("created_by") or payment.get("created_by") or "event"),
                    vendor_bank_account_id=str(vendor_bank_account_id) if vendor_bank_account_id else None,
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Treasury payment request from scheduled failed org=%s payment=%s: %s", org_id, ap_payment_id, exc
                )

    if event_type in {"bank.statement.imported", "bank.feed.imported", "bank.transaction.imported"}:
        bank_account_id = str(payload.get("bank_account_id") or "").strip()
        if bank_account_id:
            try:
                from app.modules.erp.treasury.services.bank_feed_service import bank_feed_service

                bank_feed_service.import_feed(
                    org_id,
                    bank_account_id=bank_account_id,
                    provider=str(payload.get("provider") or "stub_bank"),
                    payload=payload,
                    transactions=payload.get("transactions") if isinstance(payload.get("transactions"), list) else None,
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Bank feed import failed org=%s: %s", org_id, exc)
            try:
                from app.modules.erp.reconciliation.jobs.auto_match_job import run_auto_match

                run_auto_match(org_id, bank_account_id=bank_account_id)
            except Exception:
                pass

    if event_type == "payment.executed":
        bank_account_id = str(payload.get("bank_account_id") or "").strip()
        if bank_account_id:
            try:
                from app.modules.erp.reconciliation.jobs.auto_match_job import run_auto_match

                run_auto_match(org_id, bank_account_id=bank_account_id)
            except Exception:
                pass

    if event_type in {"receipt.received", "payment.received"}:
        bank_account_id = str(payload.get("bank_account_id") or "").strip()
        if bank_account_id:
            try:
                from app.modules.erp.reconciliation.jobs.auto_match_job import run_auto_match

                run_auto_match(org_id, bank_account_id=bank_account_id)
            except Exception:
                pass

    if event_type in {"reconciliation.completed"}:
        bank_tx_id = str(payload.get("bank_transaction_id") or "").strip()
        if bank_tx_id:
            try:
                from app.modules.erp.banking.repositories.bank_transaction_repository import bank_transaction_repository
                from app.modules.erp.treasury.jobs.cash_snapshot_job import run_cash_snapshot

                tx = bank_transaction_repository.get(org_id, transaction_id=bank_tx_id) or {}
                bank_account_id = str(tx.get("bank_account_id") or "")
                if bank_account_id:
                    run_cash_snapshot(org_id, bank_account_id=bank_account_id)
            except Exception:
                pass
        else:
            try:
                from app.modules.erp.treasury.services.cash_position_service import cash_position_service

                cash_position_service.refresh_and_emit(org_id)
            except Exception:
                pass

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_treasury_workflow_approval(org_id, payload, event_type=event_type)

    if event_type in {"erp.invoice.approved", "invoice.approved"}:
        try:
            treasury_service = __import__(
                "app.modules.erp.treasury.services.treasury_service",
                fromlist=["treasury_service"],
            ).treasury_service
            treasury_service.refresh_cash_position(org_id)
        except Exception:
            pass

    if event_type in {"payment.received", "customer.payment.received", "erp.payment.received"}:
        bank_account_id = str(payload.get("bank_account_id") or "").strip()
        amount = float(payload.get("amount") or 0)
        if bank_account_id and amount > 0:
            try:
                from app.modules.erp.treasury.services.bank_transaction_recorder import record_receipt_credit

                record_receipt_credit(
                    org_id,
                    bank_account_id=bank_account_id,
                    amount=amount,
                    reference=str(payload.get("reference") or payload.get("receipt_id") or "receipt"),
                    receipt_date=str(payload.get("payment_date") or payload.get("receipt_date") or "")[:10] or None,
                    description=str(payload.get("description") or "Customer payment received"),
                    idempotency_key=str(payload.get("idempotency_key") or f"receipt:{payload.get('receipt_id') or payload.get('entity_id')}"),
                    counterparty_ref=str(payload.get("customer_id") or ""),
                )
                from app.modules.erp.treasury.services.treasury_service import treasury_service

                treasury_service.refresh_cash_position(org_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Treasury receipt credit failed org=%s: %s", org_id, exc)

    if event_type == "webhook.received":
        entity_type = str(envelope.get("entity_type") or payload.get("entity_type") or "")
        if entity_type == "payment_gateway":
            try:
                from app.modules.erp.treasury.services.bank_feed_service import bank_feed_service

                bank_account_id = str(payload.get("bank_account_id") or "")
                if bank_account_id:
                    bank_feed_service.import_feed(
                        org_id,
                        bank_account_id=bank_account_id,
                        provider=str(payload.get("provider") or "payment_gateway"),
                        payload=payload,
                        transactions=payload.get("transactions") if isinstance(payload.get("transactions"), list) else None,
                    )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Payment gateway webhook ingest failed org=%s: %s", org_id, exc)


def _handle_tax_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    entity_type = str(payload.get("entity_type") or "").lower()
    workflow_type = str(payload.get("workflow_key") or payload.get("workflow_type") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return_id = str(payload.get("entity_id") or metadata.get("return_id") or "").strip()

    if entity_type == "tds_return" or workflow_type == "TDS_FILING":
        if not return_id:
            return False
        try:
            from app.modules.erp.tax.services.tds_return_service import tds_return_service

            tds_return_service.mark_workflow_approved(org_id, return_id=return_id)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("TDS return workflow approve failed org=%s return=%s: %s", org_id, return_id, exc)
            return False

    if entity_type == "e_invoice" or workflow_type == "EINVOICE_GENERATION":
        ar_invoice_id = str(metadata.get("ar_invoice_id") or payload.get("entity_id") or "").strip()
        if not ar_invoice_id:
            return False
        try:
            from app.modules.erp.tax.services.e_invoice_service import e_invoice_service

            e_invoice_service.mark_workflow_approved(org_id, ar_invoice_id=ar_invoice_id)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("E-invoice workflow approve failed org=%s invoice=%s: %s", org_id, ar_invoice_id, exc)
            return False

    if entity_type != "gst_return" and workflow_type != "GST_FILING":
        return False
    if not return_id:
        return False
    try:
        from app.modules.erp.tax.services.gst_return_service import gst_return_service

        gst_return_service.mark_workflow_approved(org_id, return_id=return_id)
        return True
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("GST return workflow approve failed org=%s return=%s: %s", org_id, return_id, exc)
        return False


def _handle_fiscal_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    entity_type = str(payload.get("entity_type") or "").lower()
    workflow_type = str(payload.get("workflow_key") or payload.get("workflow_type") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    period_id = str(metadata.get("period_id") or payload.get("entity_id") or "").strip()
    reopen_id = str(metadata.get("reopen_request_id") or payload.get("entity_id") or "").strip()

    if entity_type == "fiscal_period" or workflow_type == "PERIOD_CLOSE":
        if not period_id:
            return False
        try:
            from app.modules.erp.fiscal.services.close_service import close_service

            close_service.execute_close(org_id, period_id=period_id, actor_id=str(payload.get("approver_user_id") or "workflow"))
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Period close workflow failed org=%s period=%s: %s", org_id, period_id, exc)
            return False

    if entity_type == "period_reopen" or workflow_type == "PERIOD_REOPEN":
        if not reopen_id:
            return False
        try:
            from app.modules.erp.fiscal.services.reopen_service import reopen_service

            reopen_service.approve_reopen(
                org_id,
                request_id=reopen_id,
                approved_by=str(payload.get("approver_user_id") or "workflow"),
                requested_by=str(metadata.get("requested_by") or ""),
            )
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Period reopen workflow failed org=%s request=%s: %s", org_id, reopen_id, exc)
            return False
    return False


def _handle_procurement_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    entity_type = str(payload.get("entity_type") or "").lower()
    workflow_type = str(payload.get("workflow_key") or payload.get("workflow_type") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    entity_id = str(payload.get("entity_id") or "").strip()
    approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")

    if entity_type == "purchase_requisition" or workflow_type == "PR_APPROVAL":
        pr_id = str(metadata.get("pr_id") or entity_id)
        if not pr_id:
            return False
        try:
            from app.modules.erp.procurement.services.requisition_service import requisition_service

            requisition_service.mark_workflow_approved(org_id, pr_id=pr_id)
            requisition_service.approve(org_id, pr_id=pr_id, approver_id=approver, skip_workflow_check=True)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("PR workflow failed org=%s pr=%s: %s", org_id, pr_id, exc)
            return False

    if entity_type == "purchase_order" or workflow_type == "PO_APPROVAL":
        po_id = str(metadata.get("po_id") or entity_id)
        if not po_id:
            return False
        try:
            from app.modules.erp.procurement.services.po_service import po_service

            po_service.mark_workflow_approved(org_id, po_id=po_id)
            po_service.approve(org_id, po_id=po_id, approver_id=approver, skip_workflow_check=True)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("PO workflow failed org=%s po=%s: %s", org_id, po_id, exc)
            return False

    if entity_type == "goods_receipt" or workflow_type == "GRN_CONFIRMATION":
        grn_id = str(metadata.get("grn_id") or entity_id)
        if not grn_id:
            return False
        try:
            from app.modules.erp.procurement.services.grn_service import grn_service

            grn_service.mark_workflow_approved(org_id, grn_id=grn_id)
            grn_service.confirm(org_id, grn_id=grn_id, actor_id=approver, skip_workflow_check=True)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("GRN workflow failed org=%s grn=%s: %s", org_id, grn_id, exc)
            return False

    if entity_type == "procurement_exception" or workflow_type == "PROCUREMENT_EXCEPTION":
        match_id = str(metadata.get("match_id") or entity_id)
        if not match_id:
            return False
        try:
            from app.modules.erp.procurement.services.matching_service import matching_service

            matching_service.mark_exception_approved(org_id, match_id=match_id)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Procurement exception workflow failed org=%s match=%s: %s", org_id, match_id, exc)
            return False
    return False


def _handle_expense_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    entity_type = str(payload.get("entity_type") or "").lower()
    workflow_type = str(payload.get("workflow_key") or payload.get("workflow_type") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    entity_id = str(payload.get("entity_id") or "").strip()
    approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")

    if entity_type == "expense_claim" or workflow_type == "EXPENSE_CLAIM_APPROVAL":
        claim_id = str(metadata.get("claim_id") or entity_id)
        if not claim_id:
            return False
        try:
            from app.modules.erp.expenses.services.claim_service import claim_service

            claim_service.mark_workflow_approved(org_id, claim_id=claim_id)
            claim_service.approve(org_id, claim_id=claim_id, approver_id=approver, skip_workflow_check=True)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Expense claim workflow failed org=%s claim=%s: %s", org_id, claim_id, exc)
            return False

    if entity_type == "expense_policy_exception" or workflow_type == "EXPENSE_POLICY_EXCEPTION":
        claim_id = str(metadata.get("claim_id") or entity_id)
        if not claim_id:
            return False
        try:
            from app.modules.erp.expenses.repositories.claim_repository import claim_repository
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            claim_repository.set_status(org_id, claim_id=claim_id, status="submitted", workflow_approved=True)
            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "expense_claim",
                    "entity_id": claim_id,
                    "started_by": approver,
                    "metadata": metadata,
                },
            )
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Expense policy exception workflow failed org=%s claim=%s: %s", org_id, claim_id, exc
            )
            return False

    if entity_type == "expense_reimbursement" or workflow_type == "EXPENSE_REIMBURSEMENT":
        payment_request_id = str(metadata.get("payment_request_id") or entity_id)
        if not payment_request_id:
            return False
        try:
            from app.modules.erp.expenses.services.reimbursement_service import reimbursement_service

            reimbursement_service.mark_workflow_approved(org_id, payment_request_id=payment_request_id)
            reimbursement_service.execute(org_id, payment_request_id=payment_request_id, actor_id=approver)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Expense reimbursement workflow failed org=%s payment=%s: %s", org_id, payment_request_id, exc
            )
            return False
    return False


def _consume_expense_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"expense.receipt.extracted", "invoice.ai.reviewed"}:
        document_id = str(payload.get("document_id") or payload.get("invoice_id") or envelope.get("entity_id") or "").strip()
        if document_id:
            try:
                from app.modules.platform.documents.repositories.document_repository import document_repository

                doc = document_repository.get_document(org_id, document_id) or {}
                doc_type = str(doc.get("document_type") or "").lower()
                if event_type == "invoice.ai.reviewed" and doc_type not in {"receipt", "expense_receipt"}:
                    return
            except Exception:
                if event_type == "invoice.ai.reviewed":
                    return
        if document_id:
            try:
                from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
                from app.modules.erp.expenses.services.ai_expense_service import ai_expense_service

                extraction = extraction_repository.latest_extraction(org_id, document_id) or {}
                extracted = extraction.get("extracted_data") if isinstance(extraction.get("extracted_data"), dict) else {}
                if extracted:
                    employee_id = str(payload.get("employee_id") or payload.get("user_id") or "ai.expense")
                    ai_expense_service.create_from_extraction(
                        org_id,
                        extracted_data=extracted,
                        source_document_id=document_id,
                        employee_id=employee_id,
                        created_by=employee_id,
                    )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Expense claim from receipt event failed org=%s doc=%s: %s", org_id, document_id, exc
                )

    if event_type in {"ocr.completed", "document.extracted"}:
        document_id = str(payload.get("document_id") or envelope.get("entity_id") or "").strip()
        extraction_type = str(payload.get("extraction_type") or "").lower()
        if document_id and extraction_type in {"receipt_ocr", "expense_receipt"}:
            try:
                from app.modules.platform.documents.repositories.extraction_repository import extraction_repository
                from app.modules.erp.expenses.services.ai_expense_service import ai_expense_service

                extraction = extraction_repository.latest_extraction(org_id, document_id) or {}
                extracted = extraction.get("extracted_data") if isinstance(extraction.get("extracted_data"), dict) else {}
                if extracted:
                    employee_id = str(payload.get("employee_id") or payload.get("user_id") or "ai.expense")
                    ai_expense_service.create_from_extraction(
                        org_id,
                        extracted_data=extracted,
                        source_document_id=document_id,
                        employee_id=employee_id,
                        created_by=employee_id,
                    )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Expense claim from OCR event failed org=%s doc=%s: %s", org_id, document_id, exc
                )

    if event_type == "payment.executed":
        payment_request_id = str(payload.get("payment_request_id") or envelope.get("entity_id") or "").strip()
        if payment_request_id:
            try:
                from app.modules.erp.treasury.repositories.payment_request_repository import payment_request_repository
                from app.modules.erp.expenses.services.reimbursement_service import reimbursement_service

                req = payment_request_repository.get(org_id, payment_request_id=payment_request_id) or {}
                if str(req.get("payment_type") or "") == "reimbursement" and str(req.get("source_type") or "") == "expense_claim":
                    reimbursement_service.on_payment_executed(
                        org_id,
                        source_id=str(req.get("source_id") or ""),
                        payment_request_id=payment_request_id,
                    )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Expense reimbursement payment hook failed org=%s payment=%s: %s", org_id, payment_request_id, exc
                )

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_expense_workflow_approval(org_id, payload, event_type=event_type)


def _handle_asset_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    entity_type = str(payload.get("entity_type") or "").lower()
    workflow_type = str(payload.get("workflow_key") or payload.get("workflow_type") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    entity_id = str(payload.get("entity_id") or "").strip()
    approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")

    if entity_type == "asset_capitalization" or workflow_type == "ASSET_CAPITALIZATION_APPROVAL":
        asset_id = str(metadata.get("asset_id") or entity_id)
        if not asset_id:
            return False
        try:
            from app.modules.erp.assets.services.asset_service import asset_service
            from app.modules.erp.assets.services.capitalization_service import capitalization_service

            asset_service.mark_workflow_approved(org_id, asset_id=asset_id)
            capitalization_service.capitalize(org_id, asset_id=asset_id, approver_id=approver, skip_workflow_check=True)
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Asset capitalization workflow failed org=%s asset=%s: %s", org_id, asset_id, exc)
            return False

    if entity_type == "asset_disposal" or workflow_type == "ASSET_DISPOSAL_APPROVAL":
        asset_id = str(metadata.get("asset_id") or entity_id)
        sale_amount = float(metadata.get("sale_amount") or payload.get("amount") or 0)
        if not asset_id:
            return False
        try:
            from app.modules.erp.assets.repositories.asset_repository import asset_repository
            from app.modules.erp.assets.services.disposal_service import disposal_service

            asset_repository.set_status(org_id, asset_id=asset_id, status=str(
                (asset_repository.get(org_id, asset_id=asset_id) or {}).get("status") or "active"
            ), workflow_approved=True)
            disposal_service.dispose(
                org_id, asset_id=asset_id, sale_amount=sale_amount, actor_id=approver, skip_workflow_check=True
            )
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Asset disposal workflow failed org=%s asset=%s: %s", org_id, asset_id, exc)
            return False

    if entity_type == "asset_impairment" or workflow_type == "ASSET_IMPAIRMENT_APPROVAL":
        asset_id = str(metadata.get("asset_id") or entity_id)
        impairment_amount = float(metadata.get("impairment_amount") or payload.get("amount") or 0)
        if not asset_id or impairment_amount <= 0:
            return False
        try:
            from app.modules.erp.assets.repositories.asset_repository import asset_repository
            from app.modules.erp.assets.services.impairment_service import impairment_service

            asset_repository.set_status(org_id, asset_id=asset_id, status="active", workflow_approved=True)
            impairment_service.impair(
                org_id,
                asset_id=asset_id,
                impairment_amount=impairment_amount,
                actor_id=approver,
                skip_workflow_check=True,
            )
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("Asset impairment workflow failed org=%s asset=%s: %s", org_id, asset_id, exc)
            return False
    return False


def _handle_inventory_workflow_approval(org_id: str, payload: dict, *, event_type: str = "") -> bool:
    entity_type = str(payload.get("entity_type") or "").lower()
    workflow_type = str(payload.get("workflow_key") or payload.get("workflow_type") or "")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    entity_id = str(payload.get("entity_id") or "").strip()
    approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")

    if entity_type == "inventory_adjustment" or workflow_type == "INVENTORY_ADJUSTMENT_APPROVAL":
        adjustment_id = str(metadata.get("adjustment_id") or entity_id)
        item_id = str(metadata.get("item_id") or "")
        warehouse_id = str(metadata.get("warehouse_id") or "")
        quantity_variance = float(metadata.get("quantity_variance") or 0)
        value_variance = float(metadata.get("value_variance") or 0)
        adjustment_date = str(metadata.get("adjustment_date") or "")[:10] or None
        if not adjustment_id or not item_id or not warehouse_id or quantity_variance == 0:
            return False
        try:
            from datetime import date

            from app.modules.erp.inventory.services.adjustment_service import adjustment_service

            adjustment_service.mark_workflow_approved(org_id, adjustment_id=adjustment_id)
            adjustment_service.apply_from_workflow(
                org_id,
                adjustment_id=adjustment_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                quantity_variance=quantity_variance,
                value_variance=value_variance,
                adjustment_date=adjustment_date or date.today().isoformat(),
                reason=str(metadata.get("reason") or ""),
                actor_id=approver,
            )
            return True
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning(
                "Inventory adjustment workflow failed org=%s adjustment=%s: %s", org_id, adjustment_id, exc
            )
            return False
    return False


def _consume_inventory_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"grn.confirmed", "erp.grn.confirmed"}:
        grn_id = str(payload.get("grn_id") or envelope.get("entity_id") or "").strip()
        if grn_id:
            try:
                from app.modules.erp.inventory.services.receipt_service import receipt_service

                receipt_service.receive_from_grn(org_id, grn_id=grn_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Inventory receipt from GRN failed org=%s grn=%s: %s", org_id, grn_id, exc
                )

    if event_type in {"erp.invoice.approved", "invoice.approved"}:
        invoice_id = str(payload.get("invoice_id") or envelope.get("entity_id") or "").strip()
        if invoice_id:
            try:
                from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
                from app.modules.erp.inventory.repositories.movement_repository import grn_link_repository

                inv = invoice_repository.get(org_id, invoice_id=invoice_id) or {}
                grn_id = inv.get("goods_receipt_id")
                if grn_id:
                    links = grn_link_repository.list_by_grn(org_id, goods_receipt_id=str(grn_id))
                    if links and float(inv.get("invoice_amount") or 0) > 0:
                        grni_total = sum(float(l.get("total_cost") or 0) for l in links)
                        variance = float(inv.get("invoice_amount") or 0) - grni_total
                        if abs(variance) > 1.0:
                            import logging

                            logging.getLogger(__name__).info(
                                "GRNI reconciliation variance org=%s invoice=%s variance=%s",
                                org_id,
                                invoice_id,
                                variance,
                            )
            except Exception:
                pass

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_inventory_workflow_approval(org_id, payload, event_type=event_type)


def _consume_asset_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"erp.invoice.approved", "invoice.approved"}:
        invoice_id = str(payload.get("invoice_id") or envelope.get("entity_id") or "").strip()
        if invoice_id:
            try:
                from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
                from app.modules.erp.assets.services.candidate_service import candidate_service

                inv = invoice_repository.get(org_id, invoice_id=invoice_id) or {}
                candidate_service.create_from_ap_invoice(
                    org_id,
                    invoice_id=invoice_id,
                    amount=float(inv.get("invoice_amount") or inv.get("total_amount") or 0),
                    description=str(inv.get("invoice_number") or inv.get("description") or ""),
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Asset candidate from AP invoice failed org=%s invoice=%s: %s", org_id, invoice_id, exc
                )

    if event_type in {"expense.claim.approved"}:
        claim_id = str(payload.get("claim_id") or "").strip()
        amount = float(payload.get("amount") or 0)
        if claim_id and amount > 0:
            try:
                from app.modules.erp.assets.services.candidate_service import candidate_service

                candidate_service.create_from_expense_claim(
                    org_id, claim_id=claim_id, amount=amount, description=str(payload.get("claim_number") or "")
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Asset candidate from expense claim failed org=%s claim=%s: %s", org_id, claim_id, exc
                )

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_asset_workflow_approval(org_id, payload, event_type=event_type)


def _consume_fiscal_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"reconciliation.completed", "bank.reconciliation.completed"}:
        period_id = str(payload.get("period_id") or payload.get("fiscal_period_id") or "").strip()
        if period_id:
            try:
                from app.modules.erp.fiscal.services.close_service import close_service

                close_service.complete_checklist_item(
                    org_id, period_id=period_id, check_name="bank_reconciliation_complete", actor_id="event"
                )
            except Exception:
                pass

    if event_type in {"erp.gst.return.generated", "gst.return.generated"}:
        period = str(payload.get("period") or payload.get("return_period") or "")[:7]
        if period:
            try:
                from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository
                from app.modules.erp.fiscal.services.close_service import close_service

                for p in fiscal_period_repository.list(org_id, limit=50):
                    if str(p.get("start_date") or "")[:7] == period or str(p.get("end_date") or "")[:7] == period:
                        close_service.complete_checklist_item(
                            org_id, period_id=str(p["id"]), check_name="gst_validation_complete", actor_id="event"
                        )
                        break
            except Exception:
                pass

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_fiscal_workflow_approval(org_id, payload, event_type=event_type)

    if event_type == "compliance.completed":
        period = str(payload.get("return_period") or "")[:7]
        try:
            from app.modules.erp.fiscal.services.close_service import close_service
            from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository

            for p in fiscal_period_repository.list(org_id, limit=50):
                if period and (str(p.get("start_date") or "")[:7] == period or str(p.get("end_date") or "")[:7] == period):
                    close_service.complete_checklist_item(
                        org_id, period_id=str(p["id"]), check_name="compliance_obligations_complete", actor_id="event"
                    )
                    code = str(payload.get("compliance_code") or "")
                    if code.startswith("TDS"):
                        close_service.complete_checklist_item(
                            org_id, period_id=str(p["id"]), check_name="tds_returns_filed", actor_id="event"
                        )
                    break
        except Exception:
            pass


def _consume_procurement_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"erp.vendor.created", "vendor.created"}:
        return

    if event_type in {"erp.invoice.approved", "invoice.approved"}:
        invoice_id = str(payload.get("invoice_id") or envelope.get("entity_id") or "").strip()
        if invoice_id:
            try:
                from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
                from app.modules.erp.procurement.services.budget_check_service import budget_check_service
                from app.modules.erp.procurement.repositories.requisition_repository import requisition_repository
                from app.modules.erp.procurement.repositories.po_repository import po_repository

                inv = invoice_repository.get(org_id, invoice_id=invoice_id) or {}
                po = po_repository.get(org_id, po_id=str(inv.get("purchase_order_id"))) if inv.get("purchase_order_id") else None
                if po and po.get("pr_id"):
                    pr = requisition_repository.get(org_id, pr_id=str(po["pr_id"]))
                    budget_check_service.consume_spend(
                        org_id,
                        cost_center_id=pr.get("cost_center_id") if pr else None,
                        amount=float(inv.get("total_amount") or 0),
                    )
            except Exception:
                pass

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_procurement_workflow_approval(org_id, payload, event_type=event_type)


def _consume_tax_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"erp.invoice.approved", "invoice.approved"}:
        invoice_id = str(payload.get("invoice_id") or envelope.get("entity_id") or "").strip()
        if invoice_id:
            try:
                from app.modules.erp.tax.services.gst_transaction_service import gst_transaction_service

                gst_transaction_service.record_from_ap_invoice(org_id, invoice_id=invoice_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Tax AP record failed org=%s invoice=%s: %s", org_id, invoice_id, exc)

    if event_type in {"invoice.issued", "sales.invoice.issued"}:
        invoice_id = str(payload.get("invoice_id") or envelope.get("entity_id") or "").strip()
        if invoice_id:
            try:
                from app.modules.erp.tax.services.gst_transaction_service import gst_transaction_service

                gst_transaction_service.record_from_ar_invoice(org_id, invoice_id=invoice_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Tax AR record failed org=%s invoice=%s: %s", org_id, invoice_id, exc)
            try:
                from app.modules.erp.tax.services.e_invoice_service import e_invoice_service
                from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository

                e_invoice_service.maybe_auto_generate(org_id, ar_invoice_id=invoice_id)
                inv = ar_invoice_repository.get(org_id, invoice_id=invoice_id) or {}
                taxable = float(inv.get("subtotal") or 0)
                from app.modules.erp.tax.services.eway_bill_service import eway_bill_service

                eway_bill_service.maybe_auto_generate(org_id, source_type="ar_invoice", source_id=invoice_id, taxable_value=taxable)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Tax auto e-invoice/eway failed org=%s invoice=%s: %s", org_id, invoice_id, exc)

    if event_type in {"invoice.received"}:
        invoice_id = str(payload.get("invoice_id") or payload.get("ap_invoice_id") or envelope.get("entity_id") or "").strip()
        if invoice_id:
            try:
                from app.modules.erp.tax.services.gst_transaction_service import gst_transaction_service

                gst_transaction_service.record_from_ap_invoice(org_id, invoice_id=invoice_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Tax AP record from invoice.received failed org=%s: %s", org_id, exc)

    if event_type in {"receipt.received", "customer.payment.received", "payment.received"}:
        receipt_id = str(payload.get("receipt_id") or envelope.get("entity_id") or "").strip()
        if receipt_id:
            try:
                from app.modules.erp.tax.events.tax_events import emit_compliance_alert

                emit_compliance_alert(org_id, alert_type="receipt.recorded", summary=f"Customer receipt {receipt_id} recorded for compliance tracking", severity="low")
            except Exception:
                pass

    if event_type in {"erp.journal.posted", "journal.posted"}:
        source_type = str(payload.get("source_type") or "")
        source_id = str(payload.get("source_id") or envelope.get("entity_id") or "").strip()
        if source_id and source_type in {"ap_invoice", "ar_invoice"}:
            try:
                from app.modules.erp.tax.services.gst_transaction_service import gst_transaction_service

                gst_transaction_service.record_from_source(org_id, source_type=source_type, source_id=source_id)
            except Exception:
                pass

    if event_type in {"erp.payment.completed", "payment.completed"}:
        payment_id = str(payload.get("payment_id") or envelope.get("entity_id") or "").strip()
        if payment_id:
            try:
                from app.modules.erp.tax.services.tds_service import tds_service

                tds_service.calculate_for_payment(org_id, payment_id=payment_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("TDS calc failed org=%s payment=%s: %s", org_id, payment_id, exc)

    if event_type in {"payment.executed"}:
        payment_request_id = str(payload.get("payment_request_id") or envelope.get("entity_id") or "").strip()
        if payment_request_id:
            try:
                from app.modules.erp.treasury.repositories.payment_request_repository import payment_request_repository
                from app.modules.erp.tax.services.tax_treasury_bridge_service import tax_treasury_bridge_service

                req = payment_request_repository.get(org_id, payment_request_id=payment_request_id) or {}
                if str(req.get("payment_type") or "") == "tax_payment":
                    meta = req.get("metadata") if isinstance(req.get("metadata"), dict) else {}
                    tax_treasury_bridge_service.handle_tax_payment_executed(
                        org_id,
                        payment_request_id=payment_request_id,
                        amount=float(req.get("amount") or payload.get("amount") or 0),
                        metadata=meta,
                    )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("Tax treasury bridge failed org=%s payment=%s: %s", org_id, payment_request_id, exc)

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        _handle_tax_workflow_approval(org_id, payload, event_type=event_type)


def _consume_journal_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"approval.completed", "workflow.approved", "workflow.completed"}:
        ap_payment_id = str(payload.get("ap_payment_id") or "").strip()
        if not ap_payment_id:
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            ap_payment_id = str(metadata.get("ap_payment_id") or "").strip()
        if ap_payment_id:
            try:
                from app.modules.erp.accounts_payable.services.payment_service import payment_service

                payment_service.mark_workflow_approved(org_id, payment_id=ap_payment_id)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "AP payment workflow approve failed org=%s payment=%s: %s", org_id, ap_payment_id, exc
                )
            return

        if _handle_ar_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_treasury_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_tax_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_fiscal_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_procurement_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_expense_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_asset_workflow_approval(org_id, payload, event_type=event_type):
            return

        if _handle_inventory_workflow_approval(org_id, payload, event_type=event_type):
            return

        ctx = _resolve_workflow_domain_context(org_id, payload)
        ap_invoice_id = str(
            ctx.get("ap_invoice_id") or payload.get("ap_invoice_id") or payload.get("invoice_id") or payload.get("entity_id") or ""
        ).strip()
        if ap_invoice_id:
            try:
                from app.modules.erp.accounts_payable.services.invoice_service import invoice_service

                approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")
                invoice_service.approve(org_id, invoice_id=ap_invoice_id, approver_id=approver, auto_post=True)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "AP invoice approve from event failed org=%s invoice=%s: %s", org_id, ap_invoice_id, exc
                )
            return
        journal_id = str(payload.get("journal_id") or "").strip()
        if not journal_id:
            return
        try:
            from app.modules.erp.journals.services.approval_service import approval_service

            approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")
            approval_service.approve(org_id, journal_id=journal_id, approver_id=approver)
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("journal approve from event failed org=%s journal=%s: %s", org_id, journal_id, exc)

    if event_type in {"erp.payment.completed", "payment.completed"}:
        journal_id = str(payload.get("journal_id") or "").strip()
        if not journal_id:
            return
        try:
            from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator

            posting_orchestrator.post_journal(org_id, journal_id=journal_id, posted_by=str(payload.get("posted_by") or "payment"))
        except Exception as exc:
            import logging

            logging.getLogger(__name__).warning("journal post from payment event failed org=%s journal=%s: %s", org_id, journal_id, exc)


def _consume_ar_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"customer.payment.received", "payment.received"}:
        receipt_id = str(payload.get("receipt_id") or "").strip()
        if receipt_id and payload.get("auto_complete"):
            try:
                from app.modules.erp.accounts_receivable.services.collection_service import collection_service

                collection_service.complete_receipt(
                    org_id, receipt_id=receipt_id, completed_by=str(payload.get("posted_by") or "event"), auto_post=True
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "AR receipt complete from event failed org=%s receipt=%s: %s", org_id, receipt_id, exc
                )


def consume_event(queue: str, envelope: dict) -> None:
    if queue.endswith("ingestion.sync"):
        _consume_ingestion_event(envelope)
    elif queue.endswith("ingestion.retry"):
        _consume_retry_event(envelope)
    elif queue.endswith("processing.chunk"):
        _consume_chunk_processing_event(envelope)
    elif queue.endswith("processing.embed"):
        _consume_chunk_processing_event(envelope)
    elif queue.endswith("processing.extract"):
        _consume_extract_event(envelope)
    elif queue.endswith("graph.upsert"):
        _consume_graph_event(envelope)
    elif queue.endswith("memory.write"):
        _consume_memory_event(envelope)
    elif queue.endswith("retrieval.precompute"):
        _consume_memory_event(envelope)
    elif queue.endswith("agent.run"):
        _consume_agent_run_event(envelope)
    elif queue.endswith("agent.action"):
        _consume_agent_action_event(envelope)
        if str(envelope.get("event_type", "")) == "agent.action.planned":
            _consume_agent_plan_event(envelope)
    elif queue.endswith("notifications.dispatch"):
        _consume_notification_event(envelope, queue=queue)
    elif queue.endswith("audit.persist"):
        _consume_audit_event(envelope)
    elif str(envelope.get("event_type", "")) in {
        "audit.log.created",
        "policy.violation.detected",
        "policy.evaluated",
        "policy.approved",
        "policy.denied",
        "policy.override.required",
        "policy.risk.detected",
        "consolidation.completed",
        "consolidation.failed",
        "elimination.generated",
        "intercompany.created",
        "intercompany.mismatch.detected",
        "entity.closed",
        "compliance.alert.generated",
    }:
        _consume_governance_event(envelope)
    elif queue.endswith("workflow.execution"):
        _consume_workflow_execution_event(envelope)
    elif queue.endswith("workflow.sla"):
        _consume_workflow_sla_event(envelope)
    elif queue.endswith("workflow.escalations"):
        _consume_workflow_escalation_event(envelope)
    elif queue.endswith("workflow.retries"):
        _consume_workflow_execution_event(envelope)
    elif queue.endswith("workflow.approvals"):
        _consume_workflow_approval_event(envelope)
    elif queue.endswith("ai.ocr"):
        _consume_ocr_event(envelope)
    elif queue.endswith("ai.reconciliation") or queue.endswith("ai.risk") or queue.endswith("ai.forecasting"):
        _consume_ai_queue_event(envelope)
    elif queue.endswith("ai.memory"):
        _consume_memory_event(envelope)
    elif queue.endswith("integration.gst") or queue.endswith("integration.bank") or queue.endswith("integration.webhooks") or queue.endswith("integration.email"):
        _consume_integration_event(envelope)
    elif queue.endswith("notifications.email") or queue.endswith("notifications.whatsapp") or queue.endswith("notifications.push"):
        _consume_notification_event(envelope, queue=queue)
    elif queue.endswith("reports.generate") or queue.endswith("reports.refresh"):
        _consume_reports_event(envelope)
    elif "scheduler" in str(envelope.get("event_type", "")):
        _consume_scheduler_event(envelope)
    _consume_document_intelligence_event(envelope)
    _consume_document_security_event(envelope)
    _consume_coa_events(envelope)
    _consume_workflow_intelligence(envelope)
    _consume_m25_invoice_pipeline(envelope)
    _consume_memory_ingestion(envelope)
    _consume_graph_ingestion(envelope)
    _consume_agents_trigger(envelope)
    _consume_forecasting_refresh(envelope)
    _consume_reporting_refresh(envelope)
    _consume_analytics_refresh(envelope)
    _consume_audit_explorer_materialize(envelope)
    _consume_invoice_predicted(envelope)
    _consume_invoice_ai_reviewed(envelope)
    _consume_workflow_system_task_gl_post(envelope)
    _consume_journal_events(envelope)
    _consume_treasury_events(envelope)
    _consume_tax_events(envelope)
    _consume_fiscal_events(envelope)
    _consume_procurement_events(envelope)
    _consume_expense_events(envelope)
    _consume_asset_events(envelope)
    _consume_inventory_events(envelope)
    _consume_ar_events(envelope)
    _push_document_realtime(envelope)
    try:
        from app.modules.platform.notifications.services.notification_service import notification_service

        if (
            notification_service.schema_ready()
            and not queue.endswith("audit.persist")
            and _should_route_domain_notification(envelope, queue)
        ):
            notification_service.handle_event_envelope(envelope)
    except Exception:
        pass
    log_event("event.consumer.processed", queue=queue, event_type=envelope.get("event_type", ""))
