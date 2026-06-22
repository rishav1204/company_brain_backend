from __future__ import annotations

from app.core.config import settings

_INSECURE_JWT_SECRETS = frozenset(
    {
        "",
        "dev-secret-change-me",
        "change-me",
        "secret",
    }
)


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
    return len(issues) == 0, issues


def assert_prod_security() -> None:
    valid, issues = validate_prod_security()
    if valid:
        return
    raise RuntimeError(
        "Production security validation failed: " + ", ".join(issues)
    )
