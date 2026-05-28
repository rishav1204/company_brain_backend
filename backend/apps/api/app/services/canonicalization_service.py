from app.services.repositories import canonical_repo, invoices_repo


def _connector_entity_type(connector: str) -> str:
    if connector in {"erp", "bank", "docs"}:
        return "vendor"
    if connector in {"crm"}:
        return "customer"
    return "entity"


def _connector_defaults(connector: str, payload: dict) -> dict:
    if connector == "bank":
        return {
            "payment_terms": str(payload.get("payment_terms", "Due on receipt")),
            "risk_tier": str(payload.get("risk_tier", "high" if str(payload.get("risk_signal", "")).lower() == "alert" else "medium")),
            "invoice_type": str(payload.get("invoice_type", "ap")),
            "segment": str(payload.get("segment", "enterprise")),
            "payment_method": str(payload.get("payment_method", "wire")),
            "payment_status": str(payload.get("payment_status", "completed")),
        }
    if connector == "erp":
        return {
            "payment_terms": str(payload.get("payment_terms", "Net 30")),
            "risk_tier": str(payload.get("risk_tier", "medium")),
            "invoice_type": str(payload.get("invoice_type", "ap")),
            "segment": str(payload.get("segment", "mid_market")),
            "payment_method": str(payload.get("payment_method", "ach")),
            "payment_status": str(payload.get("payment_status", "pending")),
        }
    if connector == "crm":
        return {
            "payment_terms": str(payload.get("payment_terms", "Net 15")),
            "risk_tier": str(payload.get("risk_tier", "low")),
            "invoice_type": str(payload.get("invoice_type", "ar")),
            "segment": str(payload.get("segment", "enterprise")),
            "payment_method": str(payload.get("payment_method", "card")),
            "payment_status": str(payload.get("payment_status", "pending")),
        }
    if connector == "docs":
        return {
            "payment_terms": str(payload.get("payment_terms", "Net 45")),
            "risk_tier": str(payload.get("risk_tier", "medium")),
            "invoice_type": str(payload.get("invoice_type", "ap")),
            "segment": str(payload.get("segment", "vendor")),
            "payment_method": str(payload.get("payment_method", "ach")),
            "payment_status": str(payload.get("payment_status", "pending")),
        }
    return {
        "payment_terms": str(payload.get("payment_terms", "Net 30")),
        "risk_tier": str(payload.get("risk_tier", "medium")),
        "invoice_type": str(payload.get("invoice_type", "ap")),
        "segment": str(payload.get("segment", "general")),
        "payment_method": str(payload.get("payment_method", "ach")),
        "payment_status": str(payload.get("payment_status", "pending")),
    }


def _parse_amount(payload: dict) -> float | None:
    amount = payload.get("amount")
    try:
        numeric_amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        return None
    if numeric_amount is None or numeric_amount <= 0:
        return None
    return numeric_amount


def normalize_connector_payload(org_id: str, connector: str, payload: dict) -> dict:
    normalized_type = _connector_entity_type(connector)
    defaults = _connector_defaults(connector, payload)
    entity_name = str(payload.get("entity_name") or payload.get("connector") or connector).strip() or connector
    external_ref = str(payload.get("external_ref", "")).strip() or None
    entity = canonical_repo.upsert_finance_entity(
        org_id=org_id,
        entity_type=normalized_type,
        name=entity_name,
        external_ref=external_ref,
    )

    vendor = None
    customer = None
    if normalized_type == "vendor":
        vendor = canonical_repo.upsert_vendor(
            org_id=org_id,
            finance_entity_id=entity["id"],
            payment_terms=defaults["payment_terms"],
            risk_tier=defaults["risk_tier"],
        )
    elif normalized_type == "customer":
        customer = canonical_repo.upsert_customer(
            org_id=org_id,
            finance_entity_id=entity["id"],
            segment=defaults["segment"],
            risk_tier=defaults["risk_tier"],
        )

    contract = None
    contract_number = str(payload.get("contract_number", "")).strip()
    if contract_number or connector == "docs":
        contract = canonical_repo.upsert_contract(
            org_id=org_id,
            contract_number=contract_number or f"CTR-{external_ref or entity_name}",
            vendor_id=(vendor or {}).get("id"),
            start_date=payload.get("contract_start") or payload.get("start_date"),
            end_date=payload.get("contract_end") or payload.get("end_date"),
            status=str(payload.get("contract_status", "active")),
            risk_tier=defaults["risk_tier"],
        )

    purchase_order = None
    po_number = str(payload.get("po_number", "")).strip()
    if po_number or connector == "erp":
        numeric_amount = _parse_amount(payload) or 0.0
        purchase_order = canonical_repo.upsert_purchase_order(
            org_id=org_id,
            po_number=po_number or f"PO-{external_ref or entity_name}",
            vendor_id=(vendor or {}).get("id"),
            amount=numeric_amount,
            purchase_date=payload.get("purchase_date") or payload.get("due_date"),
            contract_id=(contract or {}).get("id"),
            status=str(payload.get("po_status", "open")),
        )

    invoice = None
    numeric_amount = _parse_amount(payload)
    if numeric_amount:
        invoice = invoices_repo.create_invoice(
            org_id=org_id,
            vendor_id=(vendor or {}).get("id"),
            customer_id=(customer or {}).get("id"),
            amount=numeric_amount,
            due_date=payload.get("due_date"),
            invoice_type=defaults["invoice_type"],
            purchase_order_id=(purchase_order or {}).get("id"),
        )

    payment = None
    if connector == "bank" and numeric_amount:
        payment = canonical_repo.upsert_payment(
            org_id=org_id,
            invoice_id=(invoice or {}).get("invoice_id"),
            amount=numeric_amount,
            payment_date=payload.get("payment_date") or payload.get("due_date"),
            payment_method=defaults["payment_method"],
            status=defaults["payment_status"],
        )

    journal_entry = None
    if connector == "erp" and payload.get("account_code"):
        debit = float(payload.get("debit", numeric_amount or 0))
        credit = float(payload.get("credit", 0))
        journal_entry = canonical_repo.upsert_journal_entry(
            org_id=org_id,
            period=str(payload.get("period", "current")),
            entry_date=str(payload.get("entry_date") or payload.get("due_date") or "2026-01-01"),
            account_code=str(payload.get("account_code")),
            debit=debit,
            credit=credit,
            status=str(payload.get("journal_status", "posted")),
        )

    return {
        "entity": entity,
        "vendor": vendor,
        "customer": customer,
        "contract": contract,
        "purchase_order": purchase_order,
        "invoice": invoice,
        "payment": payment,
        "journal_entry": journal_entry,
        "normalized_type": normalized_type,
    }
