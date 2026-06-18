from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.core.iam import iam_router
from app.modules.platform.documents.routes.router import documents_router
from app.modules.platform.governance.routes.router import governance_router
from app.modules.platform.notifications.routes.router import notifications_router
from app.modules.platform.integrations.routes.router import integrations_router
from app.modules.platform.integrations import connectors as _integrations_connectors  # noqa: F401
from app.modules.erp.coa.routes.router import erp_coa_router
from app.modules.erp.gl.routes.router import erp_gl_router
from app.modules.erp.journals.routes.router import erp_journals_router
from app.modules.erp.accounts_payable.routes.router import erp_ap_router
from app.modules.erp.accounts_receivable.routes.router import erp_ar_router
from app.modules.platform.governance.middleware.audit_middleware import AuditCaptureMiddleware
from app.modules.platform.governance.middleware.governance_middleware import GovernanceEnforcementMiddleware
from app.modules.platform.governance.middleware.trace_middleware import GovernanceTraceMiddleware
from app.modules.workflows.routes.router import router as workflows_router
from app.api.routes import (
    agents,
    auth,
    companies,
    connectors,
    decisions_memory,
    graph,
    ingestion,
    memory_admin,
    observability,
    ops,
    platform_events,
    platform_webhooks,
    queue,
    retrieval,
    retrieval_eval,
    sources,
    training_eval,
    workflows,
)
from app.core.config import settings
from app.middleware import RequestMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.services.observability_service import startup_observability

    startup_observability()
    if settings.postgres_dsn and settings.iam_use_db_auth:
        from app.modules.core.iam.services.iam_schema_service import core_schema_ready
        import logging

        if not core_schema_ready():
            logging.getLogger(__name__).warning(
                "IAM core schema not ready — run migrations 009+ before IAM_USE_DB_AUTH in production"
            )
        from app.modules.platform.governance.repositories.policy_repository import policy_repository

        if settings.postgres_dsn and not policy_repository.schema_ready():
            logging.getLogger(__name__).warning(
                "Governance schema not ready — run migrations 016+ (and 017 for physical audit table) in production"
            )
        from app.modules.platform.notifications.repositories.notification_repository import notification_repository

        if settings.postgres_dsn and not notification_repository.schema_ready():
            logging.getLogger(__name__).warning(
                "Notifications schema not ready — run migration 018 before production"
            )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(AuditCaptureMiddleware)
app.add_middleware(GovernanceEnforcementMiddleware)
app.add_middleware(GovernanceTraceMiddleware)
app.add_middleware(RequestMiddleware)
cors_origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(iam_router, prefix=settings.api_prefix)
app.include_router(sources.router, prefix=settings.api_prefix)
app.include_router(retrieval.router, prefix=settings.api_prefix)
app.include_router(workflows.router, prefix=settings.api_prefix)
app.include_router(workflows_router, prefix=settings.api_prefix)
app.include_router(decisions_memory.router, prefix=settings.api_prefix)
app.include_router(agents.router, prefix=settings.api_prefix)
app.include_router(governance_router, prefix=settings.api_prefix)
app.include_router(notifications_router, prefix=settings.api_prefix)
app.include_router(documents_router, prefix=settings.api_prefix)
app.include_router(integrations_router, prefix=settings.api_prefix)
app.include_router(erp_coa_router, prefix=settings.api_prefix)
app.include_router(erp_gl_router, prefix=settings.api_prefix)
app.include_router(erp_journals_router, prefix=settings.api_prefix)
app.include_router(erp_ap_router, prefix=settings.api_prefix)
app.include_router(erp_ar_router, prefix=settings.api_prefix)
app.include_router(companies.router, prefix=settings.api_prefix)
app.include_router(observability.router, prefix=settings.api_prefix)
app.include_router(ingestion.router, prefix=settings.api_prefix)
app.include_router(queue.router, prefix=settings.api_prefix)
app.include_router(memory_admin.router, prefix=settings.api_prefix)
app.include_router(graph.router, prefix=settings.api_prefix)
app.include_router(retrieval_eval.router, prefix=settings.api_prefix)
app.include_router(connectors.router, prefix=settings.api_prefix)
app.include_router(ops.router, prefix=settings.api_prefix)
app.include_router(platform_events.router, prefix=settings.api_prefix)
app.include_router(platform_webhooks.router, prefix=settings.api_prefix)
app.include_router(training_eval.router, prefix=settings.api_prefix)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.get("/ready")
def ready() -> dict:
    checks: dict[str, str] = {"api": "ok"}
    if settings.postgres_dsn:
        try:
            from app.services.db import get_db_conn

            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            checks["postgres"] = "ok"
        except Exception as exc:
            checks["postgres"] = f"error:{exc.__class__.__name__}"
    else:
        checks["postgres"] = "skipped"
    if settings.redis_url:
        try:
            import redis

            client = redis.Redis.from_url(
                settings.redis_url, decode_responses=True, socket_connect_timeout=15
            )
            client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error:{exc.__class__.__name__}"
    else:
        checks["redis"] = "skipped"
    if settings.postgres_dsn and settings.iam_use_db_auth:
        from app.modules.core.iam.services.iam_schema_service import core_schema_ready

        checks["iam_core_schema"] = "ok" if core_schema_ready() else "error:missing_core_schema"
    else:
        checks["iam_core_schema"] = "skipped"
    from app.services.observability_service import observability_status, validate_prod_observability

    obs = observability_status()
    checks["otel_ready"] = "ok" if obs["otel_ready"] else "degraded"
    checks["log_sink_configured"] = "ok" if obs["log_sink_configured"] else "skipped"
    valid, issues = validate_prod_observability()
    checks["observability"] = "ok" if valid else f"error:{','.join(issues)}"
    if any(str(value).startswith("error:") for value in checks.values()):
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "service": settings.app_name, "checks": checks}
