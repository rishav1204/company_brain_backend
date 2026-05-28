from fastapi import APIRouter, Depends, Response

from app.api.deps import build_request_context
from app.services.event_bus import event_bus
from app.services.event_queue import event_queue
from app.services.event_topology import queue_groups
from app.services.metrics import metrics_store
from app.services.observability_service import observability_status, probe_log_sink
from app.services.otel import is_otel_ready

router = APIRouter(tags=["observability"])


@router.get("/observability/status")
def observability_stack_status(probe: bool = False, context=Depends(build_request_context)) -> dict:
    status = observability_status(probe_sink=probe)
    return {
        "request_id": context.request_id,
        "status": status,
        "confidence": 1.0,
        "verification_status": "observability_stack_status",
    }


@router.get("/metrics")
def metrics(context=Depends(build_request_context)) -> dict:
    snapshot = metrics_store.snapshot()
    lag_by_queue = {queue: event_queue.lag(queue) for queue in queue_groups().values()}
    obs = observability_status()
    return {
        "request_id": context.request_id,
        "metrics": {
            "request_count": snapshot.request_count,
            "request_error_count": snapshot.request_error_count,
            "workflow_actions": snapshot.workflow_actions,
            "agent_runs": snapshot.agent_runs,
            "retrieval_queries": snapshot.retrieval_queries,
            "llm_failures": snapshot.llm_failures,
            "queue_retries": snapshot.queue_retries,
            "queue_dlq_count": snapshot.queue_dlq_count,
            "log_sink_success_count": snapshot.log_sink_success_count,
            "log_sink_failure_count": snapshot.log_sink_failure_count,
            "trace_span_count": snapshot.trace_span_count,
            "iam_login_failures": snapshot.iam_login_failures,
            "iam_login_successes": snapshot.iam_login_successes,
            "iam_permission_denials": snapshot.iam_permission_denials,
            "iam_token_refreshes": snapshot.iam_token_refreshes,
            "queue_lag_estimate": sum(max(0, value) for value in lag_by_queue.values()),
            "queue_lag_by_queue": lag_by_queue,
            "otel_enabled": is_otel_ready(),
            "log_sink_configured": obs["log_sink_configured"],
            "prod_requirements_met": obs["prod_requirements_met"],
            "workflow_transitions": snapshot.workflow_transitions,
            "workflow_approvals": snapshot.workflow_approvals,
            "workflow_sla_breaches": snapshot.workflow_sla_breaches,
            "workflow_escalations": snapshot.workflow_escalations,
            "workflow_retries": snapshot.workflow_retries,
            "governance_audits": snapshot.governance_audits,
            "governance_violations": snapshot.governance_violations,
            "governance_compliance_alerts": snapshot.governance_compliance_alerts,
            "governance_webhook_deliveries": snapshot.governance_webhook_deliveries,
            "governance_replay_ops": snapshot.governance_replay_ops,
            "workflow_latency_avg_ms": (
                snapshot.workflow_latency_ms_total // snapshot.workflow_latency_samples
                if snapshot.workflow_latency_samples
                else 0
            ),
            "approval_wait_avg_ms": (
                snapshot.approval_wait_ms_total // snapshot.approval_wait_samples
                if snapshot.approval_wait_samples
                else 0
            ),
        },
        "confidence": 1.0,
        "verification_status": "runtime_counter",
    }


@router.get("/metrics/prometheus")
def metrics_prometheus(context=Depends(build_request_context)) -> Response:
    snapshot = metrics_store.snapshot()
    lag_by_queue = {queue: event_queue.lag(queue) for queue in queue_groups().values()}
    obs = observability_status()
    lines = [
        "# HELP app_request_count total request count",
        "# TYPE app_request_count counter",
        f"app_request_count {snapshot.request_count}",
        "# HELP app_request_error_count total request errors",
        "# TYPE app_request_error_count counter",
        f"app_request_error_count {snapshot.request_error_count}",
        "# HELP app_agent_runs total agent runs",
        "# TYPE app_agent_runs counter",
        f"app_agent_runs {snapshot.agent_runs}",
        "# HELP app_retrieval_queries total retrieval queries",
        "# TYPE app_retrieval_queries counter",
        f"app_retrieval_queries {snapshot.retrieval_queries}",
        "# HELP app_llm_failures total llm failures",
        "# TYPE app_llm_failures counter",
        f"app_llm_failures {snapshot.llm_failures}",
        "# HELP app_queue_retries total queue retries",
        "# TYPE app_queue_retries counter",
        f"app_queue_retries {snapshot.queue_retries}",
        "# HELP app_queue_dlq_count total queue dlq moves",
        "# TYPE app_queue_dlq_count counter",
        f"app_queue_dlq_count {snapshot.queue_dlq_count}",
        "# HELP app_log_sink_success_count total log sink deliveries",
        "# TYPE app_log_sink_success_count counter",
        f"app_log_sink_success_count {snapshot.log_sink_success_count}",
        "# HELP app_log_sink_failure_count total log sink delivery failures",
        "# TYPE app_log_sink_failure_count counter",
        f"app_log_sink_failure_count {snapshot.log_sink_failure_count}",
        "# HELP app_trace_span_count total trace spans emitted",
        "# TYPE app_trace_span_count counter",
        f"app_trace_span_count {snapshot.trace_span_count}",
        "# HELP app_iam_login_failures total IAM login failures",
        "# TYPE app_iam_login_failures counter",
        f"app_iam_login_failures {snapshot.iam_login_failures}",
        "# HELP app_iam_login_successes total IAM login successes",
        "# TYPE app_iam_login_successes counter",
        f"app_iam_login_successes {snapshot.iam_login_successes}",
        "# HELP app_iam_permission_denials total IAM permission denials",
        "# TYPE app_iam_permission_denials counter",
        f"app_iam_permission_denials {snapshot.iam_permission_denials}",
        "# HELP app_iam_token_refreshes total IAM token refreshes",
        "# TYPE app_iam_token_refreshes counter",
        f"app_iam_token_refreshes {snapshot.iam_token_refreshes}",
        "# HELP app_workflow_transitions total workflow transitions",
        "# TYPE app_workflow_transitions counter",
        f"app_workflow_transitions {snapshot.workflow_transitions}",
        "# HELP app_workflow_approvals total workflow approvals",
        "# TYPE app_workflow_approvals counter",
        f"app_workflow_approvals {snapshot.workflow_approvals}",
        "# HELP app_workflow_latency_avg_ms average workflow completion latency",
        "# TYPE app_workflow_latency_avg_ms gauge",
        (
            f"app_workflow_latency_avg_ms "
            f"{snapshot.workflow_latency_ms_total // snapshot.workflow_latency_samples if snapshot.workflow_latency_samples else 0}"
        ),
        "# HELP app_approval_wait_avg_ms average approval wait latency",
        "# TYPE app_approval_wait_avg_ms gauge",
        (
            f"app_approval_wait_avg_ms "
            f"{snapshot.approval_wait_ms_total // snapshot.approval_wait_samples if snapshot.approval_wait_samples else 0}"
        ),
        "# HELP app_queue_lag_total total queue lag across topology",
        "# TYPE app_queue_lag_total gauge",
        f"app_queue_lag_total {sum(max(0, value) for value in lag_by_queue.values())}",
        "# HELP app_otel_enabled opentelemetry status flag",
        "# TYPE app_otel_enabled gauge",
        f"app_otel_enabled {1 if is_otel_ready() else 0}",
        "# HELP app_log_sink_configured log sink configured flag",
        "# TYPE app_log_sink_configured gauge",
        f"app_log_sink_configured {1 if obs['log_sink_configured'] else 0}",
        "# HELP app_observability_prod_requirements_met prod observability requirements met",
        "# TYPE app_observability_prod_requirements_met gauge",
        f"app_observability_prod_requirements_met {1 if obs['prod_requirements_met'] else 0}",
    ]
    for queue, lag in lag_by_queue.items():
        metric_queue = queue.replace(".", "_")
        lines.append(f'app_queue_lag{{queue="{metric_queue}"}} {lag}')
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@router.post("/observability/probe")
def observability_probe(context=Depends(build_request_context)) -> dict:
    sink_probe = probe_log_sink()
    status = observability_status(probe_sink=False)
    return {
        "request_id": context.request_id,
        "log_sink_probe": sink_probe,
        "otel_ready": status["otel_ready"],
        "prod_requirements_met": status["prod_requirements_met"],
        "confidence": 1.0,
        "verification_status": "observability_probe_completed",
    }


@router.get("/events/recent")
def recent_events(limit: int = 20, context=Depends(build_request_context)) -> dict:
    events = [event for event in event_bus.events if event["org_id"] == context.org_id]
    return {
        "request_id": context.request_id,
        "events": events[-max(1, min(limit, 100)) :],
        "confidence": 0.98,
        "verification_status": "event_stream_snapshot",
    }
