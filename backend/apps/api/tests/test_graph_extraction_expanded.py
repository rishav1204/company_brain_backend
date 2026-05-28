from app.services import graph_extraction_service as extraction_module


def test_extract_relationships_covers_finance_graph_edges(monkeypatch) -> None:
    calls = []

    def _fake_upsert(**kwargs):
        calls.append(kwargs)
        return {"status": "upserted"}

    monkeypatch.setattr(extraction_module, "upsert_graph_event", _fake_upsert)
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_invoices_with_vendor",
        lambda org_id: [{"id": "inv-1", "vendor_id": "vendor-1"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_invoices_with_purchase_order",
        lambda org_id: [{"invoice_id": "inv-1", "purchase_order_id": "po-1", "vendor_id": "vendor-1"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_payments_with_invoice",
        lambda org_id: [{"payment_id": "pay-1", "invoice_id": "inv-1"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_contracts_with_vendor",
        lambda org_id: [{"contract_id": "ctr-1", "vendor_id": "vendor-1"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_purchase_orders_with_vendor",
        lambda org_id: [{"purchase_order_id": "po-1", "vendor_id": "vendor-1"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_workflows_with_owner",
        lambda org_id: [{"workflow_id": "wf-1", "owner_user_id": "user-1", "state": "blocked", "workflow_type": "close"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_approvals",
        lambda org_id: [{"approval_id": "ap-1", "object_type": "invoice", "object_id": "inv-1", "approver_user_id": "user-2"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_decisions",
        lambda org_id: [{"decision_id": "dec-1", "decision_type": "policy"}],
    )
    monkeypatch.setattr(
        extraction_module.graph_data_repo,
        "list_journal_entries",
        lambda org_id: [{"journal_entry_id": "je-1", "account_code": "5000"}],
    )

    result = extraction_module.extract_relationships_for_org("org-demo")

    assert result["status"] == "ok"
    assert result["relationships_extracted"] >= 8
    relations = {(call.get("relation"), call.get("node_type"), call.get("to_label")) for call in calls if call.get("relation")}
    assert ("ISSUED", "Vendor", "Invoice") in relations
    assert ("RELATES_TO", "PurchaseOrder", "Invoice") in relations
    assert ("PAID_BY", "Invoice", "Payment") in relations
    assert ("GOVERNS", "Contract", "Vendor") in relations
    assert ("APPROVES", "User", "Invoice") in relations
