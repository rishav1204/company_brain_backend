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
    extract_relationships_for_org(org_id=org_id)


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


def _consume_audit_event(envelope: dict) -> None:
    from app.modules.platform.governance.services.audit_service import audit_service

    audit_service.persist_from_event_envelope(envelope)
    _consume_governance_event(envelope)


def _consume_governance_event(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
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
    elif event_type in {"scheduler.escalation.scan"}:
        _consume_workflow_escalation_event(envelope)
    elif event_type in {"scheduler.reconciliation.daily"}:
        from app.modules.platform.events.workers.reconciliation_worker import process_reconciliation_event

        process_reconciliation_event(org_id, envelope)


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
    log_event("reports.job.received", event_type=envelope.get("event_type"), org_id=envelope.get("org_id"))


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


def _consume_invoice_ai_reviewed(envelope: dict) -> None:
    """
    Wire OCR/AI completion -> AP invoice (single source of truth).
    Source event is emitted by OCR worker as `invoice.ai.reviewed`.
    """
    event_type = str(envelope.get("event_type", ""))
    if event_type != "invoice.ai.reviewed":
        return
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    if str(review.get("status", "")).lower() != "ocr_completed":
        return
    document_id = str(payload.get("invoice_id") or review.get("document_id") or "").strip()
    if not document_id:
        return
    try:
        from app.modules.platform.documents.repositories.extraction_repository import extraction_repository

        extraction = extraction_repository.latest_extraction(org_id, document_id) or {}
    except Exception:
        extraction = {}
    extracted = extraction.get("extracted_data") if isinstance(extraction.get("extracted_data"), dict) else {}
    if not extracted:
        return

    ap_invoice_id: str | None = None
    try:
        from app.modules.erp.accounts_payable.services.ai_invoice_service import ai_invoice_service

        result = ai_invoice_service.create_from_extraction(
            org_id,
            extracted_data=extracted,
            source_document_id=document_id,
            created_by="ai.invoice",
        )
        ap_invoice_id = str((result.get("invoice") or {}).get("id") or "")
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "AP invoice from invoice.ai.reviewed failed org=%s doc=%s: %s", org_id, document_id, exc
        )
        return

    if not ap_invoice_id:
        return

    try:
        from app.modules.erp.accounts_payable.services.invoice_service import invoice_service

        invoice_service.submit_for_approval(org_id, invoice_id=ap_invoice_id, actor_id="ai.invoice")
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "AP invoice submit from invoice.ai.reviewed failed org=%s invoice=%s: %s",
            org_id,
            ap_invoice_id,
            exc,
        )


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


def _consume_journal_events(envelope: dict) -> None:
    event_type = str(envelope.get("event_type", ""))
    org_id = str(envelope.get("org_id", ""))
    if not org_id:
        return
    payload = envelope.get("payload", {}) if isinstance(envelope.get("payload"), dict) else {}

    if event_type in {"invoice.extracted", "ocr.completed", "document.extracted", "invoice.received"}:
        document_id = str(payload.get("document_id") or envelope.get("entity_id") or "").strip()
        extracted = payload.get("extracted_data") if isinstance(payload.get("extracted_data"), dict) else {}
        if not document_id or not extracted:
            try:
                from app.modules.platform.documents.repositories.extraction_repository import extraction_repository

                ext = extraction_repository.latest_extraction(org_id, document_id) or {}
                extracted = ext.get("extracted_data") if isinstance(ext.get("extracted_data"), dict) else {}
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("invoice extraction lookup failed org=%s: %s", org_id, exc)
                extracted = {}
        if document_id and extracted:
            try:
                from app.modules.erp.accounts_payable.services.ai_invoice_service import ai_invoice_service

                ai_invoice_service.create_from_extraction(
                    org_id,
                    extracted_data=extracted,
                    source_document_id=document_id,
                    created_by="event.invoice.extracted",
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning("AP AI invoice failed org=%s doc=%s: %s", org_id, document_id, exc)

    if event_type in {"approval.completed", "workflow.approved"}:
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

        ar_invoice_id = str(payload.get("ar_invoice_id") or "").strip()
        if not ar_invoice_id:
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            ar_invoice_id = str(metadata.get("ar_invoice_id") or "").strip()
        if ar_invoice_id:
            try:
                from app.modules.erp.accounts_receivable.services.sales_invoice_service import sales_invoice_service

                approver = str(payload.get("approver_user_id") or payload.get("approved_by") or "workflow")
                sales_invoice_service.issue_invoice(
                    org_id, invoice_id=ar_invoice_id, issued_by=approver, auto_post=True, force_credit_approval=True
                )
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "AR invoice issue from workflow failed org=%s invoice=%s: %s", org_id, ar_invoice_id, exc
                )
            return

        ap_invoice_id = str(
            payload.get("ap_invoice_id") or payload.get("invoice_id") or payload.get("entity_id") or ""
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
    _consume_invoice_ai_reviewed(envelope)
    _consume_workflow_system_task_gl_post(envelope)
    _consume_journal_events(envelope)
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
