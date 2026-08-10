import pytest

from app.modules.platform.integrations.services.api_key_service import api_key_service


def test_integration_api_key_rejects_wildcard_scope() -> None:
    with pytest.raises(ValueError, match="Wildcard scope"):
        api_key_service.create("org-1", name="k", scopes=["*"])
