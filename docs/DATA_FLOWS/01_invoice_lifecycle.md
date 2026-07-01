# Golden Path 01 — Invoice Lifecycle

```text
Document upload (M6) → OCR/extract (M25) → AP draft (M11) → Workflow approval (M2)
  → Journal proposal (M10) → GST/TDS (M14/M21) → Payment proposal (M22) → Audit (M33)
```

## Steps

1. **Ingest** — Document stored via M6; `document.uploaded` event.
2. **M25 pipeline** — Textract/OCR, field extraction, confidence scoring.
3. **AP draft** — `ap.create_invoice_draft` (never auto-post).
4. **M2 workflow** — Maker-checker approval chain.
5. **Post (human)** — Approved journal via workflow system task only.
6. **Compliance** — GST/TDS records from posted facts.
7. **M38 role** — Copilot can `ap.list_invoices`, draft, `workflow.start`; cannot `journal.post`.

## Key events

`invoice.predicted`, `invoice.ai.reviewed`, `ap.invoice.submitted`, `journal.posted`

## Tables

`erp.ap_invoices`, `finance_os.invoice_predictions`, `finance_os.agent_executions`, `finance_os.goals` (M38)
