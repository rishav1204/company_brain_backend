import pytest

from app.services import neo4j_service as neo4j_module
from app.services.neo4j_service import Neo4jService, _validated_neo4j_uri


def test_neo4j_tls_enforcement_requires_secure_scheme(monkeypatch) -> None:
    monkeypatch.setattr(neo4j_module.settings, "neo4j_require_tls", True)
    monkeypatch.setattr(neo4j_module.settings, "neo4j_uri", "bolt://localhost:7687")
    with pytest.raises(RuntimeError, match="NEO4J_REQUIRE_TLS"):
        _validated_neo4j_uri()


def test_neo4j_tls_allows_secure_scheme(monkeypatch) -> None:
    monkeypatch.setattr(neo4j_module.settings, "neo4j_require_tls", True)
    monkeypatch.setattr(neo4j_module.settings, "neo4j_uri", "bolt+s://neo4j.example:7687")
    assert _validated_neo4j_uri() == "bolt+s://neo4j.example:7687"


def test_bootstrap_schema_includes_all_allowed_labels() -> None:
    service = Neo4jService.__new__(Neo4jService)
    queries = service._tenant_constraint_queries()
    joined = "\n".join(queries)
    for label in Neo4jService.ALLOWED_LABELS:
        assert f"FOR (n:{label}) REQUIRE (n.org_id, n.id) IS UNIQUE" in joined
    assert "DROP CONSTRAINT company_id_unique IF EXISTS" in joined


def test_upsert_node_requires_org_id() -> None:
    service = Neo4jService.__new__(Neo4jService)
    result = service.upsert_node(label="Invoice", node_id="inv-1", properties={})
    assert result["status"] == "error"
    assert "org_id is required" in result["detail"]
