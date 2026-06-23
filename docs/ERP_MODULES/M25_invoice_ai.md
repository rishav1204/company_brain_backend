# M25 — AI Invoice Intelligence Engine

## Purpose

M25 is the canonical **invoice intelligence layer** for Finance OS. It extracts, normalizes, predicts ledger/GST accounts, scores duplicates, detects anomalies, and gates AP auto-draft — **suggest/score/flag only**, never auto-post journals.

## Schema (`finance_os.*`)

Migration: `backend/migrations/050_finance_os_invoice_ai.sql`

| Table | Purpose |
|-------|---------|
| `finance_os.invoice_extractions` | Canonical enriched invoice fields per document |
| `finance_os.invoice_predictions` | Ledger and GST suggestions with confidence |
| `finance_os.invoice_anomalies` | Detected risk signals |
| `finance_os.invoice_duplicate_scores` | Weighted duplicate scoring |

## Package

`backend/apps/api/app/modules/finance_os/invoice_ai/`

- **Pipelines:** `invoice_pipeline.run()` — single orchestration entry
- **AI:** regex + LLM extractor, ledger/GST predictors, duplicate scorer, anomaly detector, confidence bands, copilot
- **Retrieval:** vendor_memory, invoice_memory, accounting_patterns (vendor/accounting reads delegate to M27 `finance_os.memory` search with document fallback)
- **Services:** extraction, prediction, duplicate, anomaly, confidence, copilot
- **Events:** `invoice.extracted`, `invoice.predicted`, `invoice.duplicate_detected`, `invoice.anomaly_detected`

## APIs (`/api/v1/finance-os/invoice-ai`)

| Method | Path | Action |
|--------|------|--------|
| POST | `/extract` | Run full pipeline for `document_id` |
| POST | `/predict` | Re-run predictions |
| GET | `/suggestions` | List predictions |
| GET | `/duplicates` | Duplicate score |
| GET | `/anomalies` | Anomaly list |
| GET | `/extractions/{id}` | Canonical extraction |
| POST | `/copilot` | Q&A on extraction |
| POST | `/confirm-duplicate` | Human duplicate decision |
| POST | `/override-prediction` | Human ledger/GST override |

Legacy: `POST /api/v1/ap/invoices/ai/from-document` runs M25 then AP draft when confidence allows.

## Pipeline flow

```
M6 upload → OCR → documents.extractions
  → M25 invoice_pipeline.run(document_id)
    → extract + normalize
    → ledger/GST predictions
    → duplicate scoring
    → anomaly detection
    → confidence band
  → emit invoice.predicted
  → AP ai_invoice_service.create_from_m25 (if auto_draft_eligible)
```

## Confidence bands

| Score | Band | AP auto-draft |
|-------|------|---------------|
| 95–100 | auto_suggest | Yes (if clean) |
| 80–94 | review_suggested | Yes (if clean) |
| 60–79 | manual_review | No |
| <60 | human_entry | No |

**Hard blocks:** `confirmed` duplicate or `high` severity anomaly.

## Cross-module integration

| Module | Role |
|--------|------|
| M6 Documents | OCR, raw extractions, embeddings |
| M11 AP | `ai_invoice_service` reads M25; workflow submit |
| M14 AR | `ar_invoice_ai_hook` stub for sales PDFs |
| M8 COA | Ledger prediction |
| M2 Workflow | Low confidence / suspected duplicate → review |
| M27 Memory | Prediction overrides, duplicate/anomaly signals → organizational memory |

## Tests

`finance_os/invoice_ai/tests/test_invoice_ai_m25.py` — 50+ unit tests.
