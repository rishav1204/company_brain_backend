from app.services.event_topology import (
    finance_topics,
    route_for_envelope,
    route_for_event_type,
    service_boundaries,
    topic_for_event_type,
)


def test_finance_topics_cover_required_contract() -> None:
    topics = finance_topics()
    assert "finance.ingest" in topics
    assert "finance.process" in topics
    assert "finance.agent" in topics
    assert "finance.action" in topics
    assert "finance.audit" in topics


def test_event_type_maps_to_finance_topic_and_queue() -> None:
    assert topic_for_event_type("source.sync.started") == "finance.ingest"
    queue_name = route_for_event_type("source.sync.started")
    assert queue_name == finance_topics()["finance.ingest"]


def test_envelope_topic_overrides_event_type_route() -> None:
    queue_name = route_for_envelope({"topic": "finance.action", "event_type": "source.sync.started"})
    assert queue_name == finance_topics()["finance.action"]


def test_service_boundaries_declare_execution_and_audit_services() -> None:
    boundaries = service_boundaries()
    assert "execution_service" in boundaries
    assert "audit_service" in boundaries
