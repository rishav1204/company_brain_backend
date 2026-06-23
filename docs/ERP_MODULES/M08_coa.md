# Module 8 — Chart of Accounts (COA) + Accounting Foundation Engine

Module 8 provides the **deterministic accounting structure foundation**: account groups, chart of accounts hierarchy, cost centers, and mappings (financial statements + GST).

This module is **suggestion-safe** (AI can suggest mappings, never auto-post) and **audit-safe** (all changes produce audit logs + events).

---

## Database (`erp.*`)

Migration: `backend/migrations/028_erp_coa_foundation.sql`

Tables (org isolated via RLS):
- `erp.account_groups`
- `erp.chart_of_accounts`
- `erp.cost_centers`
- `erp.financial_statement_mappings`
- `erp.gst_account_mappings`

Notes:
- `company_id` exists and is nullable for multi-company evolution.
- Codes are unique per `(org_id, company_id)` scope.

---

## API Reference

All routes are under: **`/api/v1/erp/*`**

### Account groups

#### `POST /account-groups`
Request:
```json
{
  "group_name": "Current Assets",
  "group_code": "ASSET_CURRENT",
  "parent_group_id": null,
  "group_type": "asset",
  "nature": "debit",
  "company_id": null
}
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "group_code": "ASSET_CURRENT", "group_type": "asset", "nature": "debit" } }
```

#### `GET /account-groups?company_id=...`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "group_name": "…", "group_code": "…" } ] }
```

#### `PUT /account-groups/{group_id}`
Update a group (immutability enforced: only name/parent can change).

Request:
```json
{ "group_name": "Current Assets (Updated)", "parent_group_id": null }
```

### Accounts (COA)

#### `POST /accounts`
Request:
```json
{
  "account_code": "2100",
  "account_name": "Input GST",
  "account_type": "gst_input",
  "group_id": "…",
  "parent_account_id": null,
  "is_postable": true,
  "currency_code": "INR",
  "company_id": null
}
```

Response:
```json
{ "request_id": "…", "item": { "id": "…", "account_code": "2100", "is_postable": true, "is_active": true } }
```

#### `GET /accounts?company_id=...`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "account_code": "…", "account_name": "…" } ] }
```

#### `PUT /accounts/{account_id}`
Update an account (immutability enforced: only name/parent can change).

Request:
```json
{ "account_name": "Cash on Hand", "parent_account_id": null }
```

#### `POST /accounts/{account_id}/deactivate`
Response:
```json
{ "request_id": "…", "item": { "id": "…", "is_active": false } }
```

Deactivation rules:
- Enforced via `erp.account_usage` guards (migration `029_erp_coa_usage_guards.sql`):
  - **cannot deactivate** if `has_balance=true` OR `used_in_journals=true`

### Cost centers

#### `POST /cost-centers`
Request:
```json
{ "cost_center_code": "ENG", "cost_center_name": "Engineering", "parent_cost_center_id": null, "company_id": null }
```

#### `GET /cost-centers`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "cost_center_code": "ENG", "cost_center_name": "Engineering" } ] }
```

#### `PUT /cost-centers/{cost_center_id}`
Request:
```json
{ "cost_center_name": "Engineering (Updated)", "parent_cost_center_id": null }
```

#### `POST /cost-centers/{cost_center_id}/deactivate`
Response:
```json
{ "request_id": "…", "item": { "id": "…", "is_active": false } }
```

### Financial statement mappings

#### `POST /financial-mappings`
Request:
```json
{ "account_id": "…", "statement_type": "balance_sheet", "reporting_category": "Current Assets", "company_id": null }
```

#### `GET /financial-mappings`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "account_id": "…", "statement_type": "balance_sheet" } ] }
```

#### `DELETE /financial-mappings/{mapping_id}`
Response:
```json
{ "request_id": "…", "item": { "deleted": true, "id": "…" } }
```

### GST account mappings

#### `POST /gst-mappings`
Request:
```json
{ "account_id": "…", "gst_type": "cgst_input", "itc_eligible": true, "company_id": null }
```

#### `GET /gst-mappings`
Response:
```json
{ "request_id": "…", "items": [ { "id": "…", "account_id": "…", "gst_type": "cgst_input", "itc_eligible": true } ] }
```

#### `DELETE /gst-mappings/{mapping_id}`
Response:
```json
{ "request_id": "…", "item": { "deleted": true, "id": "…" } }
```

### Tree + search

#### `GET /coa/tree`
Returns group tree, account tree, and cost center tree for frontend navigation + drilldowns.

#### `GET /accounts/search?q=Cash`
Searches by `account_code` or `account_name`.

### Import / export

#### `GET /coa/template`
Returns a JSON-row template + example that can be used to build Excel/CSV templates on the frontend.

#### `POST /coa/import`
Imports COA rows (creates groups + accounts). Validates duplicates and hierarchy loops before writing.

Request:
```json
{
  "rows": [
    {
      "group_code": "ASSET_CURRENT",
      "group_name": "Current Assets",
      "group_type": "asset",
      "nature": "debit",
      "parent_group_code": null,
      "account_code": "1000",
      "account_name": "Cash",
      "account_type": "cash",
      "parent_account_code": null,
      "is_postable": true,
      "currency_code": "INR"
    }
  ]
}
```

---

## Security

COA mutations require **finance admin**:
- enforced via `require_finance_admin` guard on create/update/deactivate/mappings/import endpoints.

---

## Events + audit

Events emitted (via platform event bus):
- `erp.account.created`
- `erp.account.updated`
- `erp.gst.mapping.updated`

Audit logs recorded (governance audit service):
- `erp.account_group.created`
- `erp.account.created`
- `erp.cost_center.created`
- `erp.cost_center.deactivated`
- `erp.coa.imported`

---

## UI integration notes

- Use **account groups** for category tree navigation and reporting rollups.
- Use **account `is_postable`** to prevent users selecting non-leaf nodes in posting UIs.
- AI suggestions should always be displayed as “suggested accounts” and require user confirmation.

