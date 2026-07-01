# Golden Path 03 — Payment and Banking

```text
AP approved invoice (M11) → Payment proposal (M22) → Treasury cash check (M24)
  → Workflow approval → Bank file / execution → Reconciliation (M23)
```

## Safety

`payment.execute` is **forbidden** for AI/agents. Payments flow through M2 workflows only.

## Steps

1. Approved AP invoice eligible for payment batch.
2. Treasury reads cash position (`treasury.get_cash_position`).
3. M38 Observer may block with `insufficient_cash` alternatives.
4. Payment schedule proposed → workflow.
5. Human executes payment in banking module.
6. M23 matches bank statement lines.

## M38 role

Advisory: cash position, payment postpone/split alternatives. No direct execution.
