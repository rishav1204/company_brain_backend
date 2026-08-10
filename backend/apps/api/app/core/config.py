import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from app.core.yaml_config import yaml_get

# Load apps/api/.env with override so cloud REDIS_URL in that file wins over a
# stale machine/shell REDIS_URL (e.g. leftover redis://localhost:6379).
_API_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_API_ROOT / ".env", override=True)
# Optional cwd overlay for ad-hoc exports (does not clobber keys set above).
load_dotenv(override=False)

# Seeded benchmark tenant used for local dev login and sample data.
DEV_ORG_ID = "11111111-1111-4111-8111-111111111111"


def _env_or_yaml(env_key: str, *yaml_keys: str, default: str = "") -> str:
    value = os.getenv(env_key)
    if value is not None and value != "":
        return value
    if not yaml_keys:
        return default
    yaml_value = yaml_get(*yaml_keys, default=default)
    return str(yaml_value) if yaml_value is not None else default


def _env_or_yaml_int(env_key: str, *yaml_keys: str, default: int) -> int:
    value = os.getenv(env_key)
    if value is not None and value != "":
        return int(value)
    if not yaml_keys:
        return default
    yaml_value = yaml_get(*yaml_keys, default=default)
    return int(yaml_value)


def _env_or_yaml_float(env_key: str, *yaml_keys: str, default: float) -> float:
    value = os.getenv(env_key)
    if value is not None and value != "":
        return float(value)
    if not yaml_keys:
        return default
    yaml_value = yaml_get(*yaml_keys, default=default)
    return float(yaml_value)


class Settings(BaseModel):
    app_name: str = _env_or_yaml("APP_NAME", "app", "name", default="Company Brain Finance API")
    api_prefix: str = _env_or_yaml("API_PREFIX", "app", "api_prefix", default="/api/v1")
    app_env: str = _env_or_yaml("APP_ENV", "app", "env", default="dev")
    default_confidence: float = _env_or_yaml_float("DEFAULT_CONFIDENCE", default=0.92)
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = _env_or_yaml("JWT_ALGORITHM", "auth", "jwt_algorithm", default="HS256")
    jwt_issuer: str = _env_or_yaml("JWT_ISSUER", "auth", "jwt_issuer", default="https://example-issuer")
    jwt_audience: str = _env_or_yaml("JWT_AUDIENCE", "auth", "jwt_audience", default="company-brain-api")
    jwt_jwks_url: str = _env_or_yaml("JWT_JWKS_URL", "auth", "jwt_jwks_url", default="")
    jwt_require_jwks_in_prod: bool = os.getenv("JWT_REQUIRE_JWKS_IN_PROD", "true").lower() == "true"
    jwt_require_exp: bool = os.getenv("JWT_REQUIRE_EXP", "true").lower() == "true"
    jwt_revocation_fail_closed: bool = os.getenv("JWT_REVOCATION_FAIL_CLOSED", "true").lower() == "true"
    auth_mode: str = _env_or_yaml("AUTH_MODE", "auth", "mode", default="bearer_only")
    jwt_tenant_claim: str = _env_or_yaml("JWT_TENANT_CLAIM", "auth", "tenant_claim", default="org_id")
    jwt_roles_claim: str = _env_or_yaml("JWT_ROLES_CLAIM", "auth", "roles_claim", default="roles")
    jwt_user_claim: str = _env_or_yaml("JWT_USER_CLAIM", "auth", "user_claim", default="sub")
    oidc_enabled: bool = os.getenv("OIDC_ENABLED", "false").lower() == "true"
    oidc_provider: str = os.getenv("OIDC_PROVIDER", "auth0")
    oidc_authorization_endpoint: str = os.getenv("OIDC_AUTHORIZATION_ENDPOINT", "")
    oidc_token_endpoint: str = os.getenv("OIDC_TOKEN_ENDPOINT", "")
    oidc_issuer: str = os.getenv("OIDC_ISSUER", "")
    oidc_jwks_url: str = os.getenv("OIDC_JWKS_URL", "")
    oidc_client_id: str = os.getenv("OIDC_CLIENT_ID", "")
    oidc_client_secret: str = os.getenv("OIDC_CLIENT_SECRET", "")
    oidc_redirect_uri: str = os.getenv("OIDC_REDIRECT_URI", "")
    oidc_scopes: str = os.getenv("OIDC_SCOPES", "openid profile email")
    oidc_use_pkce: bool = os.getenv("OIDC_USE_PKCE", "true").lower() == "true"
    oidc_state_ttl_seconds: int = int(os.getenv("OIDC_STATE_TTL_SECONDS", "600"))
    oidc_org_claim: str = os.getenv("OIDC_ORG_CLAIM", "org_id")
    oidc_roles_claim: str = os.getenv("OIDC_ROLES_CLAIM", "roles")
    oidc_user_claim: str = os.getenv("OIDC_USER_CLAIM", "sub")
    api_session_ttl_seconds: int = int(os.getenv("API_SESSION_TTL_SECONDS", "3600"))
    oidc_refresh_ttl_seconds: int = int(os.getenv("OIDC_REFRESH_TTL_SECONDS", "86400"))
    oidc_store_prefix: str = os.getenv("OIDC_STORE_PREFIX", "oidc")
    redis_url: str = _env_or_yaml("REDIS_URL", "queue", "redis_url", default="redis://localhost:6379")
    postgres_dsn: str = _env_or_yaml("POSTGRES_DSN", "databases", "postgres", "dsn", default="")
    postgres_require_tls: bool = os.getenv("POSTGRES_REQUIRE_TLS", "true").lower() == "true"
    postgres_pool_min: int = int(os.getenv("POSTGRES_POOL_MIN", "5"))
    postgres_pool_max: int = int(os.getenv("POSTGRES_POOL_MAX", "20"))
    redis_stream_maxlen: int = int(os.getenv("REDIS_STREAM_MAXLEN", "100000"))
    # RQ-01: financial queues require stronger retention guarantees (no approximate trim).
    redis_stream_financial_maxlen: int = int(os.getenv("REDIS_STREAM_FINANCIAL_MAXLEN", "500000"))
    redis_pool_max_connections: int = int(os.getenv("REDIS_POOL_MAX_CONNECTIONS", "20"))
    # RQ-16: Connection pool tuning
    redis_socket_connect_timeout_seconds: float = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", "2.0"))
    redis_socket_timeout_seconds: float = float(os.getenv("REDIS_SOCKET_TIMEOUT_SECONDS", "5.0"))
    redis_health_check_interval_seconds: int = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL_SECONDS", "30"))
    erp_require_company_id: bool = os.getenv("ERP_REQUIRE_COMPANY_ID", "true").lower() == "true"
    worker_service_boundary: str = os.getenv("WORKER_SERVICE_BOUNDARY", "")
    legacy_redis_queue_enabled: bool = os.getenv("LEGACY_REDIS_QUEUE_ENABLED", "false").lower() == "true"
    redis_require_tls: bool = os.getenv("REDIS_REQUIRE_TLS", "false").lower() == "true"
    neo4j_require_tls: bool = os.getenv("NEO4J_REQUIRE_TLS", "false").lower() == "true"
    queue_main_name: str = _env_or_yaml("QUEUE_MAIN_NAME", "queue", "queue_main_name", default="finance.agent.action")
    queue_dlq_name: str = _env_or_yaml("QUEUE_DLQ_NAME", "queue", "queue_dlq_name", default="finance.agent.action.dlq")
    queue_ingestion_sync: str = os.getenv("QUEUE_INGESTION_SYNC", "ingestion.sync")
    queue_ingestion_retry: str = os.getenv("QUEUE_INGESTION_RETRY", "ingestion.retry")
    queue_processing_chunk: str = os.getenv("QUEUE_PROCESSING_CHUNK", "processing.chunk")
    queue_processing_embed: str = os.getenv("QUEUE_PROCESSING_EMBED", "processing.embed")
    queue_processing_extract: str = os.getenv("QUEUE_PROCESSING_EXTRACT", "processing.extract")
    queue_graph_upsert: str = os.getenv("QUEUE_GRAPH_UPSERT", "graph.upsert")
    queue_memory_write: str = os.getenv("QUEUE_MEMORY_WRITE", "memory.write")
    queue_retrieval_precompute: str = os.getenv("QUEUE_RETRIEVAL_PRECOMPUTE", "retrieval.precompute")
    queue_agent_run: str = os.getenv("QUEUE_AGENT_RUN", "agent.run")
    queue_agent_action: str = os.getenv("QUEUE_AGENT_ACTION", "agent.action")
    queue_notifications_dispatch: str = os.getenv("QUEUE_NOTIFICATIONS_DISPATCH", "notifications.dispatch")
    queue_audit_persist: str = os.getenv("QUEUE_AUDIT_PERSIST", "audit.persist")
    queue_workflow_execution: str = os.getenv("QUEUE_WORKFLOW_EXECUTION", "workflow.execution")
    queue_workflow_approvals: str = os.getenv("QUEUE_WORKFLOW_APPROVALS", "workflow.approvals")
    queue_workflow_escalations: str = os.getenv("QUEUE_WORKFLOW_ESCALATIONS", "workflow.escalations")
    queue_workflow_sla: str = os.getenv("QUEUE_WORKFLOW_SLA", "workflow.sla")
    queue_workflow_retries: str = os.getenv("QUEUE_WORKFLOW_RETRIES", "workflow.retries")
    queue_ai_ocr: str = os.getenv("QUEUE_AI_OCR", "ai.ocr")
    queue_ai_reconciliation: str = os.getenv("QUEUE_AI_RECONCILIATION", "ai.reconciliation")
    queue_ai_risk: str = os.getenv("QUEUE_AI_RISK", "ai.risk")
    queue_ai_memory: str = os.getenv("QUEUE_AI_MEMORY", "ai.memory")
    queue_ai_forecasting: str = os.getenv("QUEUE_AI_FORECASTING", "ai.forecasting")
    queue_integration_gst: str = os.getenv("QUEUE_INTEGRATION_GST", "integration.gst")
    queue_integration_bank: str = os.getenv("QUEUE_INTEGRATION_BANK", "integration.bank")
    queue_integration_webhooks: str = os.getenv("QUEUE_INTEGRATION_WEBHOOKS", "integration.webhooks")
    queue_integration_email: str = os.getenv("QUEUE_INTEGRATION_EMAIL", "integration.email")
    queue_notifications_email: str = os.getenv("QUEUE_NOTIFICATIONS_EMAIL", "notifications.email")
    queue_notifications_whatsapp: str = os.getenv("QUEUE_NOTIFICATIONS_WHATSAPP", "notifications.whatsapp")
    queue_notifications_push: str = os.getenv("QUEUE_NOTIFICATIONS_PUSH", "notifications.push")
    queue_reports_generate: str = os.getenv("QUEUE_REPORTS_GENERATE", "reports.generate")
    queue_reports_refresh: str = os.getenv("QUEUE_REPORTS_REFRESH", "reports.refresh")
    event_queue_backend: str = os.getenv("EVENT_QUEUE_BACKEND", "redis_streams")
    event_retry_base_seconds: int = int(os.getenv("EVENT_RETRY_BASE_SECONDS", "5"))
    event_retry_max_attempts: int = int(os.getenv("EVENT_RETRY_MAX_ATTEMPTS", "5"))
    webhook_max_attempts: int = int(os.getenv("WEBHOOK_MAX_ATTEMPTS", "5"))
    event_publish_rate_limit_per_minute: int = int(os.getenv("EVENT_PUBLISH_RATE_LIMIT_PER_MINUTE", "1200"))
    neo4j_uri: str = _env_or_yaml("NEO4J_URI", "databases", "neo4j", "uri", default="bolt://localhost:7687")
    neo4j_user: str = _env_or_yaml("NEO4J_USER", "databases", "neo4j", "user", default="neo4j")
    neo4j_password: str = _env_or_yaml("NEO4J_PASSWORD", "databases", "neo4j", "password", default="password")
    llm_provider: str = _env_or_yaml("LLM_PROVIDER", "llm", "provider", default="openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_model: str = _env_or_yaml("OPENAI_MODEL", "llm", "model", default="gpt-4.1")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    llm_retry_base_ms: int = int(os.getenv("LLM_RETRY_BASE_MS", "300"))
    llm_circuit_fail_threshold: int = int(os.getenv("LLM_CIRCUIT_FAIL_THRESHOLD", "5"))
    llm_circuit_open_seconds: int = int(os.getenv("LLM_CIRCUIT_OPEN_SECONDS", "60"))
    llm_tokens_per_minute_per_org: int = int(os.getenv("LLM_TOKENS_PER_MINUTE_PER_ORG", "30000"))
    retrieval_embedding_model: str = os.getenv("RETRIEVAL_EMBEDDING_MODEL", "text-embedding-3-small")
    retrieval_chunk_size_tokens: int = _env_or_yaml_int(
        "RETRIEVAL_CHUNK_SIZE_TOKENS", "retrieval", "chunk_size_tokens", default=800
    )
    retrieval_chunk_overlap_ratio: float = _env_or_yaml_float(
        "RETRIEVAL_CHUNK_OVERLAP_RATIO", "retrieval", "chunk_overlap_ratio", default=0.25
    )
    retrieval_top_k: int = _env_or_yaml_int("RETRIEVAL_TOP_K", "retrieval", "top_k", default=5)
    retrieval_min_confidence: float = _env_or_yaml_float(
        "RETRIEVAL_MIN_CONFIDENCE", "retrieval", "min_confidence", default=0.7
    )
    integration_timeout_seconds: float = float(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "10"))
    integration_max_retries: int = int(os.getenv("INTEGRATION_MAX_RETRIES", "3"))
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")
    erp_webhook_url: str = os.getenv("ERP_WEBHOOK_URL", "")
    bank_webhook_url: str = os.getenv("BANK_WEBHOOK_URL", "")
    crm_webhook_url: str = os.getenv("CRM_WEBHOOK_URL", "")
    docs_webhook_url: str = os.getenv("DOCS_WEBHOOK_URL", "")
    ticketing_webhook_url: str = os.getenv("TICKETING_WEBHOOK_URL", "")
    jira_base_url: str = os.getenv("JIRA_BASE_URL", "")
    jira_email: str = os.getenv("JIRA_EMAIL", "")
    jira_api_token: str = os.getenv("JIRA_API_TOKEN", "")
    jira_project_key: str = os.getenv("JIRA_PROJECT_KEY", "")
    linear_api_key: str = os.getenv("LINEAR_API_KEY", "")
    linear_team_id: str = os.getenv("LINEAR_TEAM_ID", "")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from_email: str = os.getenv("SMTP_FROM_EMAIL", "")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from_email: str = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    whatsapp_api_url: str = os.getenv("WHATSAPP_API_URL", "")
    whatsapp_api_token: str = os.getenv("WHATSAPP_API_TOKEN", "")
    sms_api_url: str = os.getenv("SMS_API_URL", "")
    sms_api_token: str = os.getenv("SMS_API_TOKEN", "")
    push_api_url: str = os.getenv("PUSH_API_URL", "")
    teams_webhook_url: str = os.getenv("TEAMS_WEBHOOK_URL", "")
    notification_retry_max_attempts: int = int(os.getenv("NOTIFICATION_RETRY_MAX_ATTEMPTS", "5"))
    notification_retry_base_seconds: int = int(os.getenv("NOTIFICATION_RETRY_BASE_SECONDS", "5"))
    otel_enabled: bool = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "company-brain-api")
    otel_exporter_otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    observability_require_in_prod: bool = os.getenv("OBSERVABILITY_REQUIRE_IN_PROD", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_sink_url: str = os.getenv("LOG_SINK_URL", "")
    disable_dev_auth_routes_in_prod: bool = os.getenv("DISABLE_DEV_AUTH_ROUTES_IN_PROD", "true").lower() == "true"
    enable_dev_auth_routes: bool = os.getenv("ENABLE_DEV_AUTH_ROUTES", "false").lower() == "true"
    enable_worker_routes: bool = os.getenv("ENABLE_WORKER_ROUTES", "false").lower() == "true"
    m38_context_engine_enabled: bool = os.getenv("M38_CONTEXT_ENGINE_ENABLED", "true").lower() == "true"
    m38_read_answer_mode: bool = os.getenv("M38_READ_ANSWER_MODE", "true").lower() == "true"
    m38_working_memory: bool = os.getenv("M38_WORKING_MEMORY", "true").lower() == "true"
    m38_unified_copilot: bool = os.getenv("M38_UNIFIED_COPILOT", "true").lower() == "true"
    m38_default_runtime: bool = os.getenv("M38_DEFAULT_RUNTIME", "true").lower() == "true"
    # Phase 8 Wave 2 — runtime reliability
    m38_entity_confidence_threshold: float = float(os.getenv("M38_ENTITY_CONFIDENCE_THRESHOLD", "0.75"))
    m38_entity_min_margin: float = float(os.getenv("M38_ENTITY_MIN_MARGIN", "0.10"))
    m38_max_runtime_steps: int = int(os.getenv("M38_MAX_RUNTIME_STEPS", "50"))
    m38_retrieval_max_retries: int = int(os.getenv("M38_RETRIEVAL_MAX_RETRIES", "2"))
    m38_retrieval_retry_base_ms: int = int(os.getenv("M38_RETRIEVAL_RETRY_BASE_MS", "50"))
    m38_event_max_retries: int = int(os.getenv("M38_EVENT_MAX_RETRIES", "3"))
    m38_step_max_auto_retries: int = int(os.getenv("M38_STEP_MAX_AUTO_RETRIES", "2"))
    # Phase 8 Wave 3 — AI security / abuse protection
    m38_ai_firewall_enabled: bool = os.getenv("M38_AI_FIREWALL_ENABLED", "true").lower() == "true"
    m38_ai_firewall_block_on_detection: bool = os.getenv("M38_AI_FIREWALL_BLOCK", "true").lower() == "true"
    m38_chat_rate_limit_per_minute: int = int(os.getenv("M38_CHAT_RATE_LIMIT_PER_MINUTE", "30"))
    m38_max_tools_per_run: int = int(os.getenv("M38_MAX_TOOLS_PER_RUN", "40"))
    m38_max_plan_nodes: int = int(os.getenv("M38_MAX_PLAN_NODES", "25"))
    m38_max_context_chars: int = int(os.getenv("M38_MAX_CONTEXT_CHARS", "24000"))
    m38_max_document_instruction_scan: int = int(os.getenv("M38_MAX_DOCUMENT_INSTRUCTION_SCAN", "8000"))
    # Phase 8 Wave 5 — autonomous finance OS (governed, prep-first)
    m38_autonomy_enabled: bool = os.getenv("M38_AUTONOMY_ENABLED", "true").lower() == "true"
    m38_autonomy_start_goals: bool = os.getenv("M38_AUTONOMY_START_GOALS", "true").lower() == "true"
    m38_default_prep_only: bool = os.getenv("M38_DEFAULT_PREP_ONLY", "false").lower() == "true"
    m38_context_cache_enabled: bool = os.getenv("M38_CONTEXT_CACHE_ENABLED", "true").lower() == "true"
    m38_context_cache_ttl_seconds: int = int(os.getenv("M38_CONTEXT_CACHE_TTL_SECONDS", "45"))
    # Phase 8 Wave 6 — AI Gateway / cost intelligence
    ai_gateway_enabled: bool = os.getenv("AI_GATEWAY_ENABLED", "true").lower() == "true"
    ai_model_cheap: str = os.getenv("AI_MODEL_CHEAP", "gpt-4.1-mini")
    ai_model_strong: str = os.getenv("AI_MODEL_STRONG", "")
    ai_model_vision: str = os.getenv("AI_MODEL_VISION", "")
    ai_model_routes_json: str = os.getenv("AI_MODEL_ROUTES_JSON", "")
    ai_class_routes_json: str = os.getenv("AI_CLASS_ROUTES_JSON", "")
    ai_model_prices_json: str = os.getenv("AI_MODEL_PRICES_JSON", "")
    ai_default_context_budget_tokens: int = int(os.getenv("AI_DEFAULT_CONTEXT_BUDGET_TOKENS", "8000"))
    ai_prompt_cache_enabled: bool = os.getenv("AI_PROMPT_CACHE_ENABLED", "true").lower() == "true"
    ai_prompt_cache_ttl_seconds: int = int(os.getenv("AI_PROMPT_CACHE_TTL_SECONDS", "120"))
    ai_entity_cache_ttl_seconds: int = int(os.getenv("AI_ENTITY_CACHE_TTL_SECONDS", "60"))
    ai_budget_enforcement_enabled: bool = os.getenv("AI_BUDGET_ENFORCEMENT_ENABLED", "true").lower() == "true"
    ai_monthly_budget_usd: float = float(os.getenv("AI_MONTHLY_BUDGET_USD", "500"))
    ai_daily_budget_usd: float = float(os.getenv("AI_DAILY_BUDGET_USD", "50"))
    ai_user_daily_budget_usd: float = float(os.getenv("AI_USER_DAILY_BUDGET_USD", "20"))
    ai_goal_budget_usd: float = float(os.getenv("AI_GOAL_BUDGET_USD", "10"))
    ai_budget_soft_ratio: float = float(os.getenv("AI_BUDGET_SOFT_RATIO", "0.8"))
    dev_use_postgres: bool = os.getenv("DEV_USE_POSTGRES", "false").lower() == "true"
    allow_direct_ap_execute: bool = os.getenv("ALLOW_DIRECT_AP_EXECUTE", "false").lower() == "true"
    scheduler_org_ids: str = os.getenv("SCHEDULER_ORG_IDS", DEV_ORG_ID)
    event_queue_inflight_seconds: int = int(os.getenv("EVENT_QUEUE_INFLIGHT_SECONDS", "120"))
    # RQ-18: outbox publish dedupe guard (prevents duplicate XADD on replay)
    outbox_publish_dedupe_ttl_seconds: int = int(os.getenv("OUTBOX_PUBLISH_DEDUPE_TTL_SECONDS", str(30 * 24 * 3600)))
    # Wave 2: dual-write to Redis on request path (false = outbox-only when schema ready)
    event_outbox_dual_write: bool = os.getenv("EVENT_OUTBOX_DUAL_WRITE", "false").lower() == "true"
    # Wave 2: max outbox publish attempts before status=dead
    outbox_max_attempts: int = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10"))
    # Wave 2: require registered definition for financial events (blocks unregistered)
    event_require_registered_financial: bool = os.getenv("EVENT_REQUIRE_REGISTERED_FINANCIAL", "true").lower() == "true"
    # Wave 2: swallow domain emit failures (legacy); false logs and re-raises for financial emits
    event_financial_emit_fail_open: bool = os.getenv("EVENT_FINANCIAL_EMIT_FAIL_OPEN", "true").lower() == "true"
    # Wave 2: outbox rows older than N days → archived by retention job (manual/ops)
    outbox_archive_after_days: int = int(os.getenv("OUTBOX_ARCHIVE_AFTER_DAYS", "90"))
    # RQ-06: event deduplication windows
    consumer_dedup_ttl_days: int = int(os.getenv("CONSUMER_DEDUP_TTL_DAYS", "7"))
    consumer_dedup_financial_ttl_days: int = int(os.getenv("CONSUMER_DEDUP_FINANCIAL_TTL_DAYS", "30"))
    # RQ-05: DLQ monitoring thresholds (emit events; alerting is infra-side)
    dlq_alert_threshold: int = int(os.getenv("DLQ_ALERT_THRESHOLD", "100"))
    # RQ-19: worker throughput knobs
    worker_stream_batch_size: int = int(os.getenv("WORKER_STREAM_BATCH_SIZE", "10"))
    outbox_publish_batch_size: int = int(os.getenv("OUTBOX_PUBLISH_BATCH_SIZE", "200"))

    # Phase 5 / Wave 3: billing resilience for AI operations (INT-21)
    # When true, unexpected billing subsystem errors will not block AI operations.
    # Explicit denials (quota/credits/entitlements) still fail closed.
    billing_fail_open_ai: bool = os.getenv("BILLING_FAIL_OPEN_AI", "false").lower() == "true"
    iam_use_db_auth: bool = os.getenv("IAM_USE_DB_AUTH", "true").lower() == "true"
    iam_access_token_ttl_seconds: int = int(os.getenv("IAM_ACCESS_TOKEN_TTL_SECONDS", "900"))
    iam_refresh_token_ttl_seconds: int = int(os.getenv("IAM_REFRESH_TOKEN_TTL_SECONDS", "604800"))
    iam_skip_mfa_in_dev: bool = os.getenv("IAM_SKIP_MFA_IN_DEV", "true").lower() == "true"
    cors_allow_origins: str = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    cors_allow_credentials: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    cloudinary_cloud_name: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    cloudinary_api_key: str = os.getenv("CLOUDINARY_API_KEY", "")
    cloudinary_api_secret: str = os.getenv("CLOUDINARY_API_SECRET", "")
    cloudinary_secure: bool = os.getenv("CLOUDINARY_SECURE", "true").lower() == "true"
    cloudinary_upload_preset: str = os.getenv("CLOUDINARY_UPLOAD_PRESET", "")
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "auto")  # auto|s3|cloudinary
    documents_bucket_prefix: str = os.getenv("DOCUMENTS_BUCKET_PREFIX", "finance-docs")
    document_confidence_threshold: float = float(os.getenv("DOCUMENT_CONFIDENCE_THRESHOLD", "0.85"))
    document_retention_years: int = int(os.getenv("DOCUMENT_RETENTION_YEARS", "8"))
    clamav_enabled: bool = os.getenv("CLAMAV_ENABLED", "false").lower() == "true"
    clamav_mode: str = os.getenv("CLAMAV_MODE", "exec")
    clamav_executable: str = os.getenv("CLAMAV_EXECUTABLE", "clamscan")
    clamav_clamd_host: str = os.getenv("CLAMAV_CLAMD_HOST", "127.0.0.1")
    clamav_clamd_port: int = int(os.getenv("CLAMAV_CLAMD_PORT", "3310"))

    ocr_provider: str = os.getenv("OCR_PROVIDER", "auto")  # auto|openai_vision|pypdf|aws_textract|gcp_documentai
    ocr_hybrid_validate: bool = os.getenv("OCR_HYBRID_VALIDATE", "true").lower() == "true"

    aws_region: str = os.getenv("AWS_REGION", "")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_session_token: str = os.getenv("AWS_SESSION_TOKEN", "")
    textract_s3_bucket: str = os.getenv("TEXTRACT_S3_BUCKET", "")

    gcp_project_id: str = os.getenv("GCP_PROJECT_ID", "")
    gcp_location: str = os.getenv("GCP_LOCATION", "us")
    gcp_documentai_processor_id: str = os.getenv("GCP_DOCUMENTAI_PROCESSOR_ID", "")
    gcp_credentials_json: str = os.getenv("GCP_CREDENTIALS_JSON", "")

    api_key_pepper: str = os.getenv("API_KEY_PEPPER", "")
    integrations_credentials_key: str = os.getenv("INTEGRATIONS_CREDENTIALS_KEY", "")
    oidc_allowed_redirect_uris: str = os.getenv("OIDC_ALLOWED_REDIRECT_URIS", "")
    oidc_jit_provisioning_enabled: bool = os.getenv("OIDC_JIT_PROVISIONING_ENABLED", "false").lower() == "true"
    oidc_jit_default_role: str = os.getenv("OIDC_JIT_DEFAULT_ROLE", "viewer")
    allow_password_auth_in_prod: bool = os.getenv("ALLOW_PASSWORD_AUTH_IN_PROD", "false").lower() == "true"
    password_reset_email_enabled: bool = os.getenv("PASSWORD_RESET_EMAIL_ENABLED", "true").lower() == "true"
    app_public_base_url: str = os.getenv("APP_PUBLIC_BASE_URL", "http://localhost:3000")
    webauthn_rp_id: str = os.getenv("WEBAUTHN_RP_ID", "localhost")
    webauthn_rp_name: str = os.getenv("WEBAUTHN_RP_NAME", "FinanceOS")
    webauthn_origin: str = os.getenv("WEBAUTHN_ORIGIN", "http://localhost:3000")
    webauthn_enabled: bool = os.getenv("WEBAUTHN_ENABLED", "false").lower() == "true"
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    sse_token_ttl_seconds: int = int(os.getenv("SSE_TOKEN_TTL_SECONDS", "300"))
    integrations_api_key_rate_limit_per_minute: int = int(os.getenv("INTEGRATIONS_API_KEY_RATE_LIMIT_PER_MINUTE", "120"))
    gstn_base_url: str = os.getenv("GSTN_BASE_URL", "")
    gstn_username: str = os.getenv("GSTN_USERNAME", "")
    gstn_password: str = os.getenv("GSTN_PASSWORD", "")
    gstn_api_key: str = os.getenv("GSTN_API_KEY", "")
    irp_base_url: str = os.getenv("IRP_BASE_URL", "")
    irp_client_id: str = os.getenv("IRP_CLIENT_ID", "")
    irp_client_secret: str = os.getenv("IRP_CLIENT_SECRET", "")
    eway_base_url: str = os.getenv("EWAY_BASE_URL", "")
    eway_username: str = os.getenv("EWAY_USERNAME", "")
    eway_password: str = os.getenv("EWAY_PASSWORD", "")
    gst_connector_provider: str = os.getenv("GST_CONNECTOR_PROVIDER", "auto")
    integrations_mode: str = _env_or_yaml("INTEGRATIONS_MODE", "integrations", "mode", default="auto")
    documents_s3_bucket: str = os.getenv("DOCUMENTS_S3_BUCKET", "")
    push_api_token: str = os.getenv("PUSH_API_TOKEN", "")

    def integrations_use_stubs(self) -> bool:
        mode = (self.integrations_mode or "auto").strip().lower()
        if mode == "stub":
            return True
        if mode == "production":
            return False
        return self.app_env.strip().lower() in {"dev", "local", "test"}

    def dev_auth_routes_enabled(self) -> bool:
        if not self.enable_dev_auth_routes:
            return False
        if self.disable_dev_auth_routes_in_prod and self.app_env.lower() == "prod":
            return False
        return True

    def _cloudinary_configured(self) -> bool:
        return bool(
            self.cloudinary_cloud_name.strip()
            and self.cloudinary_api_key.strip()
            and self.cloudinary_api_secret.strip()
        )

    def _s3_storage_configured(self) -> bool:
        return bool(self.documents_s3_bucket.strip() or self.textract_s3_bucket.strip())

    def resolved_storage_provider(self) -> str:
        provider = (self.storage_provider or "auto").strip().lower()
        if provider == "s3":
            return "s3"
        if provider == "cloudinary":
            return "cloudinary"
        if self._s3_storage_configured():
            return "s3"
        if self._cloudinary_configured():
            return "cloudinary"
        return "s3"


settings = Settings()
