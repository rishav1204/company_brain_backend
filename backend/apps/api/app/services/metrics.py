from dataclasses import dataclass
from threading import Lock


@dataclass
class MetricsSnapshot:
    request_count: int
    request_error_count: int
    workflow_actions: int
    agent_runs: int
    retrieval_queries: int
    llm_failures: int
    queue_retries: int
    queue_dlq_count: int
    log_sink_success_count: int
    log_sink_failure_count: int
    trace_span_count: int
    iam_login_failures: int
    iam_login_successes: int
    iam_permission_denials: int
    iam_token_refreshes: int
    workflow_transitions: int
    workflow_approvals: int
    workflow_sla_breaches: int
    workflow_escalations: int
    workflow_retries: int
    workflow_latency_ms_total: int
    workflow_latency_samples: int
    approval_wait_ms_total: int
    approval_wait_samples: int
    events_published: int
    events_processed: int
    governance_audits: int
    governance_violations: int
    governance_compliance_alerts: int
    governance_webhook_deliveries: int
    governance_replay_ops: int
    notifications_sent: int
    notifications_failed: int
    notification_delivery_latency_ms_total: int
    notification_delivery_latency_samples: int
    notification_realtime_connections: int
    gl_postings: int
    gl_posting_failures: int
    gl_posting_latency_ms_total: int
    gl_posting_latency_samples: int


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self.request_count = 0
        self.request_error_count = 0
        self.workflow_actions = 0
        self.agent_runs = 0
        self.retrieval_queries = 0
        self.llm_failures = 0
        self.queue_retries = 0
        self.queue_dlq_count = 0
        self.log_sink_success_count = 0
        self.log_sink_failure_count = 0
        self.trace_span_count = 0
        self.iam_login_failures = 0
        self.iam_login_successes = 0
        self.iam_permission_denials = 0
        self.iam_token_refreshes = 0
        self.workflow_transitions = 0
        self.workflow_approvals = 0
        self.workflow_sla_breaches = 0
        self.workflow_escalations = 0
        self.workflow_retries = 0
        self.workflow_latency_ms_total = 0
        self.workflow_latency_samples = 0
        self.approval_wait_ms_total = 0
        self.approval_wait_samples = 0
        self.events_published = 0
        self.events_processed = 0
        self.governance_audits = 0
        self.governance_violations = 0
        self.governance_compliance_alerts = 0
        self.governance_webhook_deliveries = 0
        self.governance_replay_ops = 0
        self.notifications_sent = 0
        self.notifications_failed = 0
        self.notification_delivery_latency_ms_total = 0
        self.notification_delivery_latency_samples = 0
        self.notification_realtime_connections = 0
        self.gl_postings = 0
        self.gl_posting_failures = 0
        self.gl_posting_latency_ms_total = 0
        self.gl_posting_latency_samples = 0
        self._queue_lag: dict[str, int] = {}
        self._queue_dlq_lag: dict[str, int] = {}

    def incr_request(self) -> None:
        with self._lock:
            self.request_count += 1

    def incr_request_error(self) -> None:
        with self._lock:
            self.request_error_count += 1

    def incr_workflow_action(self) -> None:
        with self._lock:
            self.workflow_actions += 1

    def incr_agent_run(self) -> None:
        with self._lock:
            self.agent_runs += 1

    def incr_retrieval_query(self) -> None:
        with self._lock:
            self.retrieval_queries += 1

    def incr_llm_failure(self) -> None:
        with self._lock:
            self.llm_failures += 1

    def incr_queue_retry(self) -> None:
        with self._lock:
            self.queue_retries += 1

    def incr_queue_dlq(self) -> None:
        with self._lock:
            self.queue_dlq_count += 1

    def incr_log_sink_success(self) -> None:
        with self._lock:
            self.log_sink_success_count += 1

    def incr_log_sink_failure(self) -> None:
        with self._lock:
            self.log_sink_failure_count += 1

    def incr_trace_span(self) -> None:
        with self._lock:
            self.trace_span_count += 1

    def incr_iam_login_failure(self) -> None:
        with self._lock:
            self.iam_login_failures += 1

    def incr_iam_login_success(self) -> None:
        with self._lock:
            self.iam_login_successes += 1

    def incr_iam_permission_denied(self) -> None:
        with self._lock:
            self.iam_permission_denials += 1

    def incr_iam_token_refresh(self) -> None:
        with self._lock:
            self.iam_token_refreshes += 1

    def incr_workflow_transition(self) -> None:
        with self._lock:
            self.workflow_transitions += 1

    def incr_workflow_approval(self, _decision: str = "") -> None:
        with self._lock:
            self.workflow_approvals += 1

    def incr_workflow_sla_breach(self) -> None:
        with self._lock:
            self.workflow_sla_breaches += 1

    def incr_workflow_escalation(self) -> None:
        with self._lock:
            self.workflow_escalations += 1

    def incr_workflow_retry(self) -> None:
        with self._lock:
            self.workflow_retries += 1

    def record_workflow_latency(self, duration_ms: int) -> None:
        with self._lock:
            self.workflow_latency_ms_total += max(0, duration_ms)
            self.workflow_latency_samples += 1

    def record_approval_wait(self, duration_ms: int) -> None:
        with self._lock:
            self.approval_wait_ms_total += max(0, duration_ms)
            self.approval_wait_samples += 1

    def incr_event_published(self) -> None:
        with self._lock:
            self.events_published += 1

    def incr_event_processed(self) -> None:
        with self._lock:
            self.events_processed += 1

    def incr_governance_audit(self) -> None:
        with self._lock:
            self.governance_audits += 1

    def incr_governance_violation(self) -> None:
        with self._lock:
            self.governance_violations += 1

    def incr_governance_compliance_alert(self) -> None:
        with self._lock:
            self.governance_compliance_alerts += 1

    def incr_governance_webhook_delivery(self) -> None:
        with self._lock:
            self.governance_webhook_deliveries += 1

    def incr_governance_replay(self) -> None:
        with self._lock:
            self.governance_replay_ops += 1

    def incr_notification_sent(self) -> None:
        with self._lock:
            self.notifications_sent += 1

    def incr_notification_failed(self) -> None:
        with self._lock:
            self.notifications_failed += 1

    def incr_gl_posting(self) -> None:
        with self._lock:
            self.gl_postings += 1

    def incr_gl_posting_failure(self) -> None:
        with self._lock:
            self.gl_posting_failures += 1

    def observe_gl_posting_latency_ms(self, latency_ms: int) -> None:
        with self._lock:
            self.gl_posting_latency_ms_total += int(latency_ms)
            self.gl_posting_latency_samples += 1

    def record_notification_delivery_latency(self, latency_ms: int) -> None:
        with self._lock:
            self.notification_delivery_latency_ms_total += latency_ms
            self.notification_delivery_latency_samples += 1

    def incr_notification_realtime_connection(self) -> None:
        with self._lock:
            self.notification_realtime_connections += 1

    def record_queue_lag(self, queue: str, lag: int, dlq_lag: int = 0) -> None:
        with self._lock:
            self._queue_lag[queue] = lag
            self._queue_dlq_lag[queue] = dlq_lag

    def queue_lag_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._queue_lag)

    def queue_dlq_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._queue_dlq_lag)

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(
                request_count=self.request_count,
                request_error_count=self.request_error_count,
                workflow_actions=self.workflow_actions,
                agent_runs=self.agent_runs,
                retrieval_queries=self.retrieval_queries,
                llm_failures=self.llm_failures,
                queue_retries=self.queue_retries,
                queue_dlq_count=self.queue_dlq_count,
                log_sink_success_count=self.log_sink_success_count,
                log_sink_failure_count=self.log_sink_failure_count,
                trace_span_count=self.trace_span_count,
                iam_login_failures=self.iam_login_failures,
                iam_login_successes=self.iam_login_successes,
                iam_permission_denials=self.iam_permission_denials,
                iam_token_refreshes=self.iam_token_refreshes,
                workflow_transitions=self.workflow_transitions,
                workflow_approvals=self.workflow_approvals,
                workflow_sla_breaches=self.workflow_sla_breaches,
                workflow_escalations=self.workflow_escalations,
                workflow_retries=self.workflow_retries,
                workflow_latency_ms_total=self.workflow_latency_ms_total,
                workflow_latency_samples=self.workflow_latency_samples,
                approval_wait_ms_total=self.approval_wait_ms_total,
                approval_wait_samples=self.approval_wait_samples,
                events_published=self.events_published,
                events_processed=self.events_processed,
                governance_audits=self.governance_audits,
                governance_violations=self.governance_violations,
                governance_compliance_alerts=self.governance_compliance_alerts,
                governance_webhook_deliveries=self.governance_webhook_deliveries,
                governance_replay_ops=self.governance_replay_ops,
                notifications_sent=self.notifications_sent,
                notifications_failed=self.notifications_failed,
                notification_delivery_latency_ms_total=self.notification_delivery_latency_ms_total,
                notification_delivery_latency_samples=self.notification_delivery_latency_samples,
                notification_realtime_connections=self.notification_realtime_connections,
                gl_postings=self.gl_postings,
                gl_posting_failures=self.gl_posting_failures,
                gl_posting_latency_ms_total=self.gl_posting_latency_ms_total,
                gl_posting_latency_samples=self.gl_posting_latency_samples,
            )


metrics_store = MetricsStore()
