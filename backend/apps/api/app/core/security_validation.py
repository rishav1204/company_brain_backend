from __future__ import annotations

import os

from app.core.config import settings

_INSECURE_JWT_SECRETS = frozenset(
    {
        "",
        "dev-secret-change-me",
        "change-me",
        "secret",
    }
)

_INSECURE_NEO4J_PASSWORDS = frozenset({"password", "neo4j", ""})


def validate_prod_security() -> tuple[bool, list[str]]:
    """Fail-fast checks for production security configuration."""
    if settings.app_env.lower() != "prod":
        return True, []

    issues: list[str] = []
    if settings.jwt_secret.strip() in _INSECURE_JWT_SECRETS:
        issues.append("jwt_secret_insecure_or_missing")
    if settings.auth_mode.strip().lower() != "bearer_only":
        issues.append("auth_mode_must_be_bearer_only_in_prod")
    if settings.dev_auth_routes_enabled():
        issues.append("dev_auth_routes_enabled_in_prod")
    if not settings.oidc_enabled and not settings.allow_password_auth_in_prod:
        issues.append("oidc_disabled_and_password_auth_not_allowed_in_prod")
    if not settings.api_key_pepper.strip():
        issues.append("api_key_pepper_missing_in_prod")
    if not settings.redis_url.strip():
        issues.append("redis_url_missing_in_prod")
    if not settings.redis_require_tls:
        issues.append("redis_tls_not_required_in_prod")
    if settings.neo4j_password.strip() in _INSECURE_NEO4J_PASSWORDS:
        issues.append("neo4j_password_insecure_in_prod")
    if settings.webauthn_enabled and not settings.webauthn_origin.strip():
        issues.append("webauthn_origin_missing_when_enabled")
    if settings.iam_skip_mfa_in_dev:
        issues.append("iam_skip_mfa_in_dev_enabled_in_prod")
    if not settings.clamav_enabled:
        issues.append("clamav_not_enabled_in_prod")
    else:
        # Wave 3: no compile-time import of platform.documents into shared kernel.
        # Runtime importlib keeps prod clamav probe without domain coupling at module graph.
        import importlib

        try:
            scan_mod = importlib.import_module(
                "app.modules.platform.documents.services.malware_scan_service"
            )
            ok, detail = scan_mod.verify_clamav_available()
            if not ok:
                issues.append(f"clamav_unreachable_in_prod:{detail}")
        except Exception as exc:  # pragma: no cover - optional subsystem
            issues.append(f"clamav_probe_failed:{exc}")
    if not settings.integrations_credentials_key.strip():
        issues.append("integrations_credentials_key_missing_for_secret_encryption")
    if not settings.erp_require_company_id:
        issues.append("erp_require_company_id_must_be_true_in_prod")
    if not settings.integrations_use_stubs():
        if not settings.gstn_base_url.strip():
            issues.append("gstn_connector_production_missing_gstn_base_url")
        if not os.getenv("NSDL_TDS_BASE_URL", "").strip():
            issues.append("tds_connector_production_missing_nsdl_base_url")
        if not os.getenv("BANK_API_BASE_URL", "").strip():
            issues.append("bank_connector_production_missing_bank_api_base_url")
    return len(issues) == 0, issues


def assert_prod_security() -> None:
    valid, issues = validate_prod_security()
    if valid:
        return
    raise RuntimeError(
        "Production security validation failed: " + ", ".join(issues)
    )
