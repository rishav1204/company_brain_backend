"""
Phase 1 Wave 4 — Canonical runtime & legacy inventory (source of truth for fitness tests).

Do not invent modules; only paths that exist in the repository should appear here.
"""

from __future__ import annotations

# Routes under app/api/routes mounted in main.py (legacy HTTP surface).
LEGACY_ROUTE_MODULES: frozenset[str] = frozenset(
    {
        "auth.py",
        "workflows.py",
        "agents.py",
        "graph.py",
        "decisions_memory.py",
        "memory_admin.py",
        "ingestion.py",
        "retrieval.py",
        "sources.py",
        "queue.py",
        "platform_events.py",
        "platform_webhooks.py",
        "connectors.py",
        "companies.py",
        "observability.py",
        "ops.py",
        "retrieval_eval.py",
        "training_eval.py",
        "audit.py",
    }
)

# ERP alias routers defined in code but intentionally NOT mounted in main.py (Wave 4 finding).
UNMOUNTED_ALIAS_ROUTER_SYMBOLS: frozenset[str] = frozenset(
    {
        "app.modules.erp.banking.routes.router.legacy_banking_router",
        "app.modules.erp.treasury.routes.treasury_router.legacy_treasury_router",
        "app.modules.erp.reconciliation.routes.router.legacy_reconciliation_alias",
    }
)

# Single business-implementation owners (not necessarily only HTTP entry).
CANONICAL_RUNTIME: dict[str, str] = {
    "journal_posting": "modules.erp.journals.services + posting_orchestrator + gl.posting_service",
    "authentication": "modules.core.iam (auth_service, oidc, mfa, webauthn) + services.jwt_auth decode",
    "workflows": "modules.workflows",
    "ai_runtime": "modules.finance_os.platform_ai_runtime (+ services.ai_gateway for LLM gateway)",
    "graph": "modules.finance_os.graph (neo4j_service remains shared infrastructure)",
    "memory": "modules.finance_os.memory",
    "events": "modules.platform.events (event_bus is compatibility shim)",
    "worker_orchestration": "services.worker_service + cmd/worker.py",
    "scheduler": "services.scheduler_service + cmd/scheduler.py + platform.events.scheduling_service",
    "billing": "modules.platform.billing",
    "documents_dms": "modules.platform.documents",
    "erp_command_bridge": "modules.finance_os.bridges.erp_command_bridge",
}

# Shared-kernel infrastructure services (not legacy business domains).
INFRA_SERVICES_KEEP: frozenset[str] = frozenset(
    {
        "db.py",
        "redis_client.py",
        "logger.py",
        "metrics.py",
        "trace.py",
        "otel.py",
        "rate_limiter.py",
        "schema_registry.py",
        "principal_context.py",
        "object_context.py",
        "event_topology.py",
        "event_org_validation.py",
        "redis_queue_service.py",
        "cache",
        "ai_gateway",
        "llm_provider.py",
        "llm_runtime.py",
        "jwt_auth.py",
        "observability_service.py",
        "worker_service.py",
        "scheduler_service.py",
        "idempotency.py",
        "iam_idempotency.py",
        "repository_pagination.py",
        "neo4j_service.py",
    }
)

# app/services files that are compatibility shims or legacy domain surfaces.
LEGACY_OR_SHIM_SERVICES: frozenset[str] = frozenset(
    {
        "event_bus.py",  # shim → platform_event_service
        "oidc_service.py",  # shim → IAM OIDC
        "event_consumers.py",  # facade
        "event_consumers_handlers.py",  # residual handlers / reexport
        "event_consumers_router.py",  # router glue
        "event_queue.py",
        "langgraph_runner.py",
        "memory_service.py",
        "graph_service.py",
        "graph_extraction_service.py",
        "policy_service.py",
        "action_service.py",
        "processing_service.py",
        "ingestion_service.py",
        "retrieval_service.py",
        "retrieval_pipeline.py",
        "integration_service.py",
        "queue_service.py",
        "repositories.py",
        "legacy_repos",
        "legacy_write_guard.py",
        "dev_auth_store.py",
        "dev_workflows.py",
        "in_memory_store.py",
    }
)

SUNSET_UTC = "2026-12-31T23:59:59Z"
