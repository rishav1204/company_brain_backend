import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    app_name: str = "Company Brain Finance API"
    api_prefix: str = "/api/v1"
    app_env: str = os.getenv("APP_ENV", "dev")
    default_confidence: float = 0.92
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_issuer: str = os.getenv("JWT_ISSUER", "https://example-issuer")
    jwt_audience: str = os.getenv("JWT_AUDIENCE", "company-brain-api")
    jwt_jwks_url: str = os.getenv("JWT_JWKS_URL", "")
    jwt_require_jwks_in_prod: bool = os.getenv("JWT_REQUIRE_JWKS_IN_PROD", "true").lower() == "true"
    jwt_require_exp: bool = os.getenv("JWT_REQUIRE_EXP", "true").lower() == "true"
    auth_mode: str = os.getenv("AUTH_MODE", "bearer_only")
    jwt_tenant_claim: str = os.getenv("JWT_TENANT_CLAIM", "org_id")
    jwt_roles_claim: str = os.getenv("JWT_ROLES_CLAIM", "roles")
    jwt_user_claim: str = os.getenv("JWT_USER_CLAIM", "sub")
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
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "")
    postgres_require_tls: bool = os.getenv("POSTGRES_REQUIRE_TLS", "true").lower() == "true"
    redis_require_tls: bool = os.getenv("REDIS_REQUIRE_TLS", "false").lower() == "true"
    neo4j_require_tls: bool = os.getenv("NEO4J_REQUIRE_TLS", "false").lower() == "true"
    queue_main_name: str = os.getenv("QUEUE_MAIN_NAME", "finance.agent.action")
    queue_dlq_name: str = os.getenv("QUEUE_DLQ_NAME", "finance.agent.action.dlq")
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
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    llm_retry_base_ms: int = int(os.getenv("LLM_RETRY_BASE_MS", "300"))
    llm_circuit_fail_threshold: int = int(os.getenv("LLM_CIRCUIT_FAIL_THRESHOLD", "5"))
    llm_circuit_open_seconds: int = int(os.getenv("LLM_CIRCUIT_OPEN_SECONDS", "60"))
    llm_tokens_per_minute_per_org: int = int(os.getenv("LLM_TOKENS_PER_MINUTE_PER_ORG", "30000"))
    retrieval_embedding_model: str = os.getenv("RETRIEVAL_EMBEDDING_MODEL", "text-embedding-3-small")
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
    enable_dev_auth_routes: bool = os.getenv("ENABLE_DEV_AUTH_ROUTES", "true").lower() == "true"
    enable_worker_routes: bool = os.getenv("ENABLE_WORKER_ROUTES", "true").lower() == "true"
    dev_use_postgres: bool = os.getenv("DEV_USE_POSTGRES", "false").lower() == "true"
    scheduler_org_ids: str = os.getenv("SCHEDULER_ORG_IDS", "org-demo")
    event_queue_inflight_seconds: int = int(os.getenv("EVENT_QUEUE_INFLIGHT_SECONDS", "120"))
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

    integrations_credentials_key: str = os.getenv("INTEGRATIONS_CREDENTIALS_KEY", "")
    integrations_api_key_rate_limit_per_minute: int = int(os.getenv("INTEGRATIONS_API_KEY_RATE_LIMIT_PER_MINUTE", "120"))

    def dev_auth_routes_enabled(self) -> bool:
        if not self.enable_dev_auth_routes:
            return False
        if self.disable_dev_auth_routes_in_prod and self.app_env.lower() == "prod":
            return False
        return True


settings = Settings()

# Seeded benchmark tenant used for local dev login and sample data.
DEV_ORG_ID = "11111111-1111-4111-8111-111111111111"
