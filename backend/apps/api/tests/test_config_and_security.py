from app.core.config import DEV_ORG_ID, settings
from app.core.security_validation import validate_prod_security
from app.core.yaml_config import load_yaml_config, yaml_get


def test_yaml_config_loads_retrieval_defaults() -> None:
    load_yaml_config.cache_clear()
    assert yaml_get("retrieval", "chunk_size_tokens", default=0) == 800
    assert settings.retrieval_chunk_size_tokens == 800


def test_scheduler_defaults_to_dev_org_id() -> None:
    assert settings.scheduler_org_ids == DEV_ORG_ID or "11111111" in settings.scheduler_org_ids


def test_prod_security_rejects_insecure_jwt(monkeypatch) -> None:
    monkeypatch.setattr("app.core.security_validation.settings.app_env", "prod")
    monkeypatch.setattr("app.core.security_validation.settings.jwt_secret", "dev-secret-change-me")
    monkeypatch.setattr("app.core.security_validation.settings.auth_mode", "bearer_only")
    monkeypatch.setattr("app.core.security_validation.settings.enable_dev_auth_routes", False)

    valid, issues = validate_prod_security()
    assert not valid
    assert "jwt_secret_insecure_or_missing" in issues
