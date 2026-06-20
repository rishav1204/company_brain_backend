from __future__ import annotations

"""AR hook stub — sales invoice PDFs can use M25 pipeline with invoice_type=sales."""


def process_sales_document(org_id: str, *, document_id: str) -> dict:
    from app.modules.finance_os.invoice_ai.pipelines.invoice_pipeline import invoice_pipeline

    return invoice_pipeline.run(org_id, document_id=document_id, invoice_type="sales")
