# Module 11 — Voucher Engine

## Status

**Required before production** — document entry layer above M10 Journal Engine.

## Purpose

Tally-style financial document entry that **never posts to GL directly**. All accounting truth flows:

```text
Voucher → validate → workflow → journal_generation_service → M10 → GL
```

AP/AR/Banking operational modules also **project** linked voucher rows into the unified register when they create journals.

## API

Base prefix: `/api/v1/erp/vouchers`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/erp/vouchers` | Create voucher (generic) |
| GET | `/erp/vouchers` | List vouchers |
| GET | `/erp/vouchers/{id}` | Get voucher with lines |
| POST | `/erp/vouchers/{id}/validate` | Run validation |
| POST | `/erp/vouchers/{id}/submit` | Start `VOUCHER_APPROVAL` workflow |
| POST | `/erp/vouchers/{id}/approve` | Approve and generate journal |
| POST | `/erp/vouchers/{id}/generate-journal` | Generate M10 journal only |
| POST | `/erp/vouchers/{id}/post` | Post linked journal |
| POST | `/erp/vouchers/{id}/reverse` | Reverse posted voucher |
| POST | `/erp/vouchers/{id}/cancel` | Cancel draft |

Typed shortcuts: `/erp/vouchers/sales`, `/purchase`, `/payment`, `/receipt`, `/contra`, `/journal`.

## Voucher types

| Type | Prefix | Journal type |
|------|--------|--------------|
| sales | SAL | sales |
| purchase | PUR | purchase |
| payment | PAY | payment |
| receipt | REC | receipt |
| contra | CNT | contra |
| journal | JRN | general |
| debit_note | DBN | adjustment |
| credit_note | CRN | adjustment |

## Database

- `erp.vouchers`, `erp.voucher_lines`, `erp.voucher_sequences`
- `erp.journals.voucher_id` back-link
- `erp.ap_invoices.voucher_id`, `erp.ar_invoices.voucher_id`, `erp.ap_payments.voucher_id`
- CN/DN: `document_type`, `reference_invoice_id` on AP/AR invoice tables (migration 063)

## Workflows

| Entity | Workflow key |
|--------|----------------|
| voucher | `VOUCHER_APPROVAL` |
| ap_credit_note | `AP_CREDIT_NOTE_APPROVAL` |
| ap_debit_note | `AP_DEBIT_NOTE_APPROVAL` |
| ar_credit_note | `AR_CREDIT_NOTE_APPROVAL` |

## Events

- `erp.voucher.created`
- `erp.voucher.validated`
- `erp.voucher.submitted`
- `erp.voucher.approved`
- `erp.voucher.journal_generated`
- `erp.voucher.posted`
- `erp.voucher.reversed`
- `erp.voucher.cancelled`

## Integration points

| Module | Integration |
|--------|-------------|
| M8 COA | Account validation on lines |
| M9 GL | Post only via M10 |
| M10 Journal | Sole posting path via `journal_generation_service` |
| M12 Fiscal | Period gate at validate/post |
| M2 Workflow | `VOUCHER_APPROVAL` + note workflows |
| M13 AP | Projection on approve; CN/DN note entities |
| M14 AR | Projection on issue/receipt; CN/DN note entities |
| M22 Banking | Contra projection on internal transfer |
| M25 Invoice AI | Draft purchase voucher from extraction |

## Code layout

`backend/apps/api/app/modules/erp/vouchers/`
