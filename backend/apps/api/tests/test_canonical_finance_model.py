from app.services import canonicalization_service as canonical_module


def test_erp_normalization_creates_vendor_po_invoice_and_journal(monkeypatch) -> None:
    captured = {"invoice": None, "po": None, "journal": None}

    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_finance_entity",
        lambda **kwargs: {"id": "entity-1", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_vendor",
        lambda **kwargs: {"id": "vendor-1", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_contract",
        lambda **kwargs: {"id": "contract-1", **kwargs},
    )

    def _upsert_po(**kwargs):
        captured["po"] = kwargs
        return {"id": "po-1", **kwargs}

    monkeypatch.setattr(canonical_module.canonical_repo, "upsert_purchase_order", _upsert_po)

    def _create_invoice(**kwargs):
        captured["invoice"] = kwargs
        return {"invoice_id": "inv-1", "status": "Pending"}

    monkeypatch.setattr(canonical_module.invoices_repo, "create_invoice", _create_invoice)

    def _upsert_journal(**kwargs):
        captured["journal"] = kwargs
        return {"id": "je-1", **kwargs}

    monkeypatch.setattr(canonical_module.canonical_repo, "upsert_journal_entry", _upsert_journal)

    result = canonical_module.normalize_connector_payload(
        org_id="org-demo",
        connector="erp",
        payload={
            "entity_name": "Acme Supplies",
            "external_ref": "ERP-100",
            "amount": 2500,
            "due_date": "2026-05-01",
            "po_number": "PO-9001",
            "account_code": "5000",
            "debit": 2500,
        },
    )

    assert result["normalized_type"] == "vendor"
    assert result["vendor"]["id"] == "vendor-1"
    assert result["purchase_order"]["id"] == "po-1"
    assert result["invoice"]["invoice_id"] == "inv-1"
    assert result["journal_entry"]["id"] == "je-1"
    assert captured["invoice"]["purchase_order_id"] == "po-1"
    assert captured["po"]["po_number"] == "PO-9001"


def test_crm_normalization_creates_customer_invoice(monkeypatch) -> None:
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_finance_entity",
        lambda **kwargs: {"id": "entity-2", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_customer",
        lambda **kwargs: {"id": "customer-1", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_contract",
        lambda **kwargs: {"id": "contract-2", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_purchase_order",
        lambda **kwargs: {"id": "po-2", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.invoices_repo,
        "create_invoice",
        lambda **kwargs: {"invoice_id": "inv-2", "status": "Pending", **kwargs},
    )

    result = canonical_module.normalize_connector_payload(
        org_id="org-demo",
        connector="crm",
        payload={"entity_name": "Globex", "external_ref": "CRM-22", "amount": 900, "due_date": "2026-05-10"},
    )

    assert result["normalized_type"] == "customer"
    assert result["customer"]["id"] == "customer-1"
    assert result["invoice"]["invoice_id"] == "inv-2"


def test_bank_normalization_creates_payment(monkeypatch) -> None:
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_finance_entity",
        lambda **kwargs: {"id": "entity-3", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_vendor",
        lambda **kwargs: {"id": "vendor-3", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_contract",
        lambda **kwargs: {"id": "contract-3", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_purchase_order",
        lambda **kwargs: {"id": "po-3", **kwargs},
    )
    monkeypatch.setattr(
        canonical_module.invoices_repo,
        "create_invoice",
        lambda **kwargs: {"invoice_id": "inv-3", "status": "Pending"},
    )
    monkeypatch.setattr(
        canonical_module.canonical_repo,
        "upsert_payment",
        lambda **kwargs: {"id": "pay-3", **kwargs},
    )

    result = canonical_module.normalize_connector_payload(
        org_id="org-demo",
        connector="bank",
        payload={"entity_name": "Bank Vendor", "amount": 1500, "payment_date": "2026-05-02"},
    )

    assert result["payment"]["id"] == "pay-3"
    assert result["invoice"]["invoice_id"] == "inv-3"
