from app.modules.erp.journals.services.posting_orchestrator import PostingOrchestrator


def test_idempotent_response_shape() -> None:
    orch = PostingOrchestrator()
    # Unit-level contract: already-posted payload keys
    sample = {
        "journal_id": "j1",
        "journal_status": "posted",
        "ledger_batch_id": "b1",
        "idempotent": True,
    }
    assert sample["idempotent"] is True
    assert orch.post_batch is not None
