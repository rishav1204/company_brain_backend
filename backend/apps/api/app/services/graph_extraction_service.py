from app.services.graph_service import upsert_graph_event
from app.services.repositories import graph_data_repo


def _object_label(object_type: str) -> str:
    mapping = {
        "invoice": "Invoice",
        "workflow": "Workflow",
        "payment": "Payment",
        "purchase_order": "PurchaseOrder",
        "contract": "Contract",
    }
    return mapping.get(object_type.lower(), "Workflow")


def extract_relationships_for_org(org_id: str) -> dict:
    extracted = 0

    for invoice in graph_data_repo.list_invoices_with_vendor(org_id=org_id):
        invoice_id = invoice["id"]
        upsert_graph_event(org_id=org_id, node_type="Invoice", node_id=invoice_id)
        vendor_id = invoice.get("vendor_id")
        if vendor_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="Vendor",
                node_id=vendor_id,
                relation="ISSUED",
                target_id=invoice_id,
                to_label="Invoice",
            )
        extracted += 1

    for row in graph_data_repo.list_invoices_with_purchase_order(org_id=org_id):
        po_id = row.get("purchase_order_id")
        invoice_id = row.get("invoice_id")
        if po_id and invoice_id:
            upsert_graph_event(org_id=org_id, node_type="PurchaseOrder", node_id=po_id)
            upsert_graph_event(
                org_id=org_id,
                node_type="PurchaseOrder",
                node_id=po_id,
                relation="RELATES_TO",
                target_id=invoice_id,
                to_label="Invoice",
            )
            extracted += 1

    for payment in graph_data_repo.list_payments_with_invoice(org_id=org_id):
        payment_id = payment["payment_id"]
        invoice_id = payment.get("invoice_id")
        upsert_graph_event(org_id=org_id, node_type="Payment", node_id=payment_id)
        if invoice_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="Invoice",
                node_id=invoice_id,
                relation="PAID_BY",
                target_id=payment_id,
                to_label="Payment",
            )
        extracted += 1

    for contract in graph_data_repo.list_contracts_with_vendor(org_id=org_id):
        contract_id = contract["contract_id"]
        upsert_graph_event(org_id=org_id, node_type="Contract", node_id=contract_id)
        vendor_id = contract.get("vendor_id")
        if vendor_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="Contract",
                node_id=contract_id,
                relation="GOVERNS",
                target_id=vendor_id,
                to_label="Vendor",
            )
        extracted += 1

    for po in graph_data_repo.list_purchase_orders_with_vendor(org_id=org_id):
        vendor_id = po.get("vendor_id")
        if vendor_id:
            upsert_graph_event(org_id=org_id, node_type="PurchaseOrder", node_id=po["purchase_order_id"])
            upsert_graph_event(
                org_id=org_id,
                node_type="Vendor",
                node_id=vendor_id,
                relation="REFERENCES",
                target_id=po["purchase_order_id"],
                to_label="PurchaseOrder",
            )
            extracted += 1

    for workflow in graph_data_repo.list_workflows_with_owner(org_id=org_id):
        upsert_graph_event(org_id=org_id, node_type="Workflow", node_id=workflow["workflow_id"])
        owner_user_id = workflow.get("owner_user_id")
        if owner_user_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="User",
                node_id=owner_user_id,
                relation="ASSIGNED_TO",
                target_id=workflow["workflow_id"],
                to_label="Workflow",
            )
        if workflow.get("state") == "blocked":
            incident_id = f"incident-{workflow['workflow_id']}"
            upsert_graph_event(org_id=org_id, node_type="Incident", node_id=incident_id)
            upsert_graph_event(
                org_id=org_id,
                node_type="Workflow",
                node_id=workflow["workflow_id"],
                relation="BLOCKED_BY",
                target_id=incident_id,
                to_label="Incident",
            )
        extracted += 1

    for approval in graph_data_repo.list_approvals(org_id=org_id):
        approver_user_id = approval.get("approver_user_id")
        object_id = approval.get("object_id")
        object_type = str(approval.get("object_type", "")).lower()
        if approver_user_id and object_id:
            target_label = _object_label(object_type)
            upsert_graph_event(org_id=org_id, node_type="User", node_id=approver_user_id)
            upsert_graph_event(
                org_id=org_id,
                node_type="User",
                node_id=approver_user_id,
                relation="APPROVES",
                target_id=object_id,
                to_label=target_label,
            )
            extracted += 1

    for decision in graph_data_repo.list_decisions(org_id=org_id):
        decision_id = decision["decision_id"]
        upsert_graph_event(org_id=org_id, node_type="Decision", node_id=decision_id)
        kpi_id = f"kpi-{decision.get('decision_type', 'general')}"
        upsert_graph_event(
            org_id=org_id,
            node_type="Decision",
            node_id=decision_id,
            relation="IMPACTS",
            target_id=kpi_id,
            to_label="KPI",
        )
        extracted += 1

    for journal in graph_data_repo.list_journal_entries(org_id=org_id):
        upsert_graph_event(org_id=org_id, node_type="KPI", node_id=f"gl-{journal['account_code']}")
        extracted += 1

    for invoice in graph_data_repo.list_erp_ap_invoices_with_vendor(org_id=org_id):
        invoice_id = invoice["invoice_id"]
        upsert_graph_event(org_id=org_id, node_type="Invoice", node_id=invoice_id)
        vendor_id = invoice.get("vendor_id")
        if vendor_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="Vendor",
                node_id=vendor_id,
                relation="ISSUED",
                target_id=invoice_id,
                to_label="Invoice",
            )
        extracted += 1

    for payment in graph_data_repo.list_erp_ap_payments_with_allocations(org_id=org_id):
        payment_id = payment["payment_id"]
        invoice_id = payment.get("invoice_id")
        upsert_graph_event(org_id=org_id, node_type="Payment", node_id=payment_id)
        if invoice_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="Invoice",
                node_id=invoice_id,
                relation="PAID_BY",
                target_id=payment_id,
                to_label="Payment",
            )
        extracted += 1

    for journal in graph_data_repo.list_erp_journals_with_source(org_id=org_id):
        journal_id = journal["journal_id"]
        upsert_graph_event(org_id=org_id, node_type="Journal", node_id=journal_id)
        source_id = journal.get("source_id")
        if source_id and journal.get("source_type") == "invoice":
            upsert_graph_event(
                org_id=org_id,
                node_type="Invoice",
                node_id=source_id,
                relation="GENERATED",
                target_id=journal_id,
                to_label="Journal",
            )
        extracted += 1

    for bt in graph_data_repo.list_erp_bank_transactions(org_id=org_id):
        upsert_graph_event(org_id=org_id, node_type="BankTransaction", node_id=bt["bank_transaction_id"])
        extracted += 1

    for gst in graph_data_repo.list_erp_gst_returns(org_id=org_id):
        upsert_graph_event(org_id=org_id, node_type="GSTReturn", node_id=gst["gst_return_id"])
        extracted += 1

    for asset in graph_data_repo.list_erp_assets_with_source(org_id=org_id):
        asset_id = asset["asset_id"]
        invoice_id = asset.get("source_invoice_id")
        upsert_graph_event(org_id=org_id, node_type="Asset", node_id=asset_id)
        if invoice_id:
            upsert_graph_event(
                org_id=org_id,
                node_type="Invoice",
                node_id=invoice_id,
                relation="CAPITALIZED_AS",
                target_id=asset_id,
                to_label="Asset",
            )
        extracted += 1

    return {"status": "ok", "relationships_extracted": extracted}
