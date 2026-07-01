# IAM ABAC Rules

## Branch + amount example

Finance Manager can approve payments below ₹5L for Bangalore branch only.

Assign role `policy_context`:

```json
{
  "max_approve_amount": 500000,
  "rules": [
    {
      "resource": "payment",
      "action": "payment.approve",
      "condition": {
        "amount_lte": 500000,
        "branch_amount_outside_limit": 500000
      }
    }
  ]
}
```

Scope the role to a branch via `user_roles.branch_id`.

## Department scoping

Create departments in `core.departments` and assign `user_roles.department_id`.
Login merges `allowed_department_ids` into JWT `attrs`.

## Enforcement points

- Payment/treasury approve routes call `evaluate_access` with `amount` and `branch_id`.
- Workflow guards use `evaluate_access` with workflow context.
- M38 ERP tools enforce `policy_action` via the tool registry.
