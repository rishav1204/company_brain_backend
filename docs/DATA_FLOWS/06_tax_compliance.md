# Golden Path 06 — Tax Compliance

```text
Posted transactions (M10) → GST engine (M14) → TDS (M20) → Compliance calendar (M21)
```

## Flow

1. Journals post (workflow-only) → GST liability computed.
2. TDS deductions on applicable AP payments.
3. M21 compliance calendar tracks due dates and filings.
4. AI may **read** compliance status; `gst.file` is forbidden.

## Events

`journal.posted`, `gst.return.due`, compliance scheduler ticks.
