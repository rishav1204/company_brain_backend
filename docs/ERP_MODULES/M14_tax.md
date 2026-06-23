# Module 14 — GST, Taxation & Compliance Engine

## Purpose
Enterprise Tax & Compliance OS for GST, TDS, e-invoicing, e-way bills, ITC, returns filing, compliance calendar, and AI-assisted tax operations. Consumes AP/AR/Treasury/GL data — does not duplicate accounting engines.

**Migrations:** `036_erp_tax_engine.sql`, `037_erp_tax_compliance.sql`, `038_erp_tax_gap_closure.sql`

## APIs

### GST (`/api/v1/gst`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/gst/registrations` | Register org GSTIN |
| GET | `/gst/registrations` | List registrations |
| POST | `/gst/calculate` | Preview CGST/SGST/IGST split |
| GET | `/gst/transactions` | GST transaction ledger |
| GET | `/gst/itc` | ITC ledger |
| GET | `/gst/itc/summary` | ITC summary (optional `return_period`) |
| POST | `/gst/itc/{id}/claim` | Claim ITC (maker-checker via `tax.modify`) |
| GET/POST/PATCH | `/gst/itc/blocked-rules` | Configure blocked ITC rules |
| GET/POST | `/gst/rates` | GST rate master |
| POST | `/gst/returns/generate` | Generate GSTR-1, GSTR-3B, or GSTR-9 |
| GET | `/gst/returns` | List returns |
| GET | `/gst/returns/{id}` | Get return |
| POST | `/gst/returns/{id}/submit` | Submit for GST_FILING workflow |
| POST | `/gst/returns/{id}/file` | File return (manual after approval) |
| POST | `/gst/reconciliation/import-2b` | Import GSTR-2B data |
| POST | `/gst/reconciliation/run` | Run 2B reconciliation |
| GET | `/gst/reconciliation` | List reconciliation results |
| POST | `/gst/reconciliation/{id}/resolve` | Resolve mismatch |
| POST | `/gst/e-invoice/{invoice_id}/generate` | Generate IRN |
| GET | `/gst/e-invoice/{invoice_id}` | Get e-invoice |
| POST | `/gst/e-invoice/{invoice_id}/cancel` | Cancel IRN |
| POST | `/gst/eway-bill/generate` | Generate e-way bill |
| GET | `/gst/eway-bill/{id}` | Get e-way bill |
| POST | `/gst/eway-bill/{id}/cancel` | Cancel e-way bill |

### TDS (`/api/v1/tds`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/tds/transactions` | List TDS deductions |
| GET | `/tds/sections` | Configurable TDS sections |
| POST | `/tds/calculate` | Preview TDS calculation |
| POST | `/tds/returns/generate` | Generate Form 26Q payload |
| GET | `/tds/returns` | List TDS returns |
| GET | `/tds/returns/{id}` | Get TDS return |
| POST | `/tds/returns/{id}/submit` | Submit TDS_FILING workflow |
| POST | `/tds/returns/{id}/file` | File TDS return (maker-checker) |

### Compliance (`/api/v1/compliance` — aliases; primary M21: `/api/v1/erp/compliance`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/compliance/calendar` | **Alias** → M21 obligations calendar |
| POST | `/compliance/calendar/seed` | **Alias** → M21 seed |
| GET | `/compliance/calendar/upcoming` | **Alias** → M21 upcoming |
| GET | `/erp/compliance/*` | **Primary** M21 compliance engine (see M21_compliance.md) |
| POST | `/compliance/notices` | Store tax notice (+ Document Intelligence OCR) |
| GET | `/compliance/notices` | List notices |
| GET | `/compliance/risk` | Tax risk assessment |
| POST | `/compliance/copilot` | AI compliance Q&A |

## Data flow

```text
AP invoice approved / AR invoice issued / invoice.received
  → gst_transaction_service (purchase/sales/credit_note/debit_note/RCM/import)
  → erp.gst_transactions + erp.itc_ledger (purchases)
  → gst.transaction.recorded event

AR invoice issued (B2B)
  → auto e-invoice IRN (configurable) + optional EINVOICE_GENERATION workflow
  → auto e-way bill when taxable value ≥ ₹50k

GSTR-1 / GSTR-3B / GSTR-9 generate from ledger → emit erp.gst.return.generated
  → GST_FILING workflow → manual file via M7 stub_gst / gstn provider

GSTR-2B import → reconciliation → gst.mismatch.detected + vendor filing flags

AP payment completed → tds_service (section from vendor/payment metadata)
TDS return generate → TDS_FILING workflow → file

Treasury tax_payment executed → M21 `complete_by_source(GST_PAYMENT)` + compliance.alert

scheduler.compliance.daily → M21 generate + status refresh + reminders + escalations
```

## Events

### Emitted
- `gst.transaction.recorded`, `erp.gst.return.generated` (on generate + file)
- `gst.mismatch.detected`, `tds.calculated`, `irn.generated`, `eway.bill.created`
- `compliance.alert` (deadlines, mismatches, tax payments, TDS filing)

### Consumed
- `erp.invoice.approved` → purchase GST + ITC
- `invoice.issued` → sales GST + auto e-invoice/e-way
- `invoice.received` → AP GST pre-record
- `receipt.received` → compliance tracking alert
- `erp.journal.posted` → backfill
- `payment.completed` → TDS calculation
- `payment.executed` → treasury tax_payment bridge
- `workflow.approved` → GST/TDS/e-invoice workflow approval
- `scheduler.compliance.daily` → calendar deadline scan

## M7 Integration
- `stub_gst` — returns + IRN/e-way stubs
- `gstn` — GSTN portal provider stub
- `gstn_irp` — dedicated IRP connector (`irp_connector.py`)
- `stub_eway` — e-way bill connector
- Canonical models: `CanonicalGSTReturn`, `CanonicalEInvoice`, `CanonicalEwayBill`

## Blueprint compliance audit

| Requirement | Status |
|-------------|--------|
| GST registrations + GSTIN validation | ✅ |
| GST transaction ledger (all document types) | ✅ |
| Place of supply (GSTIN + AR address + B2C) | ✅ |
| HSN/SAC from invoice lines/metadata | ✅ |
| GST rate master (configurable) | ✅ |
| ITC ledger + blocked rules CRUD API | ✅ |
| ITC summary by return period | ✅ |
| GSTR-1 / GSTR-3B / GSTR-9 + emit on generate | ✅ |
| AP reverse-charge journal (RCM Payable) | ✅ |
| POST /gst/calculate preview API | ✅ |
| gst_posting_service facade (purchase/sale/RCM) | ✅ |
| Production GSTN/IRP/e-way connectors (env-configured) | ✅ |
| GSTR-2B reconciliation + vendor filing flags | ✅ |
| Auto e-invoice + EINVOICE workflow | ✅ |
| IRN writeback to AR invoice metadata | ✅ |
| E-way auto + cancel APIs | ✅ |
| TDS calc + section selection + 26Q returns | ✅ |
| TDS rule engine (tds_rules) + no-PAN 20% logic | ✅ |
| TDS deduct on AP payment + 3-line journal | ✅ |
| TDS challans + liability/vendor-summary APIs | ✅ |
| Form 16A JSON generation | ✅ |
| 26Q/27Q/27EQ/24Q return builders | ✅ |
| TCS 206C engine + AR invoice hook | ✅ |
| 26AS reconciliation upload | ✅ |
| TDS scheduler jobs (challan reminder, Form 16A) | ✅ |
| Form 16A PDF + DMS storage | ✅ |
| NSDL/FVU filing connectors (env-configured) | ✅ |
| TDS COA auto-provision (tds/tcs payable) | ✅ |
| TDS AI assistants (recommend, review, copilot) | ✅ |
| TDS_FILING workflow + maker-checker | ✅ |
| Compliance calendar + scheduler job | ✅ |
| Treasury tax_payment → GSTR-3B calendar | ✅ |
| Notice + Document Intelligence OCR | ✅ |
| IAM tax.read/file/modify + roles | ✅ |
| Maker-checker (gst.file, tds.file, tax.modify) | ✅ |
| compliance.alert events | ✅ |
| filing_service facade | ✅ |
| Unit tests (31 tax / 111 ERP) | ✅ |

**Compliance: ~98%** — Production NSDL TDS filing requires `NSDL_TDS_*` env credentials; Form 16A PDF is system-generated (not legally signed); TDS AI is heuristic not LLM.
