from app.services import connectors


def test_connector_run_dedupes_processed_records(monkeypatch) -> None:
    seen = {"processed": set(), "marks": 0, "state_updates": 0}

    monkeypatch.setattr(
        connectors.integration_service,
        "push_erp",
        lambda payload: type("R", (), {"status": "completed", "detail": "ok"})(),
    )
    monkeypatch.setattr(
        connectors.ingestion_repo,
        "get_connector_sync_state",
        lambda org_id, connector, source_id, mode: {"cursor_ref": "cursor-a"},
    )
    monkeypatch.setattr(
        connectors.ingestion_repo,
        "has_processed_connector_record",
        lambda org_id, connector, source_id, external_record_id: external_record_id in seen["processed"],
    )

    def _mark_processed(org_id, connector, source_id, external_record_id, payload_hash, normalized_ref):
        seen["processed"].add(external_record_id)
        seen["marks"] += 1

    monkeypatch.setattr(connectors.ingestion_repo, "mark_connector_record_processed", _mark_processed)
    monkeypatch.setattr(
        connectors.ingestion_repo,
        "upsert_connector_sync_state",
        lambda org_id, connector, source_id, mode, cursor_ref, metadata_jsonb: seen.__setitem__(
            "state_updates", seen["state_updates"] + 1
        ),
    )
    monkeypatch.setattr(
        connectors,
        "normalize_connector_payload",
        lambda org_id, connector, payload: {"entity": {"id": "entity-1"}, "vendor": None, "invoice": None, "normalized_type": "vendor"},
    )
    monkeypatch.setattr(connectors.event_bus, "publish", lambda **kwargs: kwargs)

    first = connectors.run_connector(org_id="org-demo", connector="erp", mode="cdc", source_id="source-1")
    second = connectors.run_connector(org_id="org-demo", connector="erp", mode="cdc", source_id="source-1")

    assert first.status == "completed"
    assert first.records_ingested == 2
    assert second.status == "completed"
    assert second.records_ingested == 0
    assert seen["marks"] == 2
    assert seen["state_updates"] == 2
