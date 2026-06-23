# Module 17 — Fixed Assets Management Engine

## Purpose
Enterprise asset lifecycle: capitalization, straight-line depreciation, transfer, impairment, disposal with full journal integration via M10/M9 and fiscal gating via M12.

**Migration:** `042_erp_assets_engine.sql`

## APIs (`/api/v1/erp/assets`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `` | Create draft asset |
| GET | ``, `/{id}` | List/get assets |
| POST | `/{id}/submit` | Submit for capitalization workflow |
| POST | `/{id}/capitalize` | Post capitalization journal → `active` |
| POST | `/depreciate` | Batch monthly depreciation run |
| POST | `/{id}/depreciate` | Depreciate single asset |
| GET | `/{id}/depreciation` | Depreciation history |
| POST | `/{id}/transfer` | Transfer department/location/custodian (no GL) |
| POST | `/{id}/impair` | Record impairment + journal |
| POST | `/{id}/dispose` | Dispose asset + gain/loss journal |
| GET | `/register` | Fixed asset register report |
| GET | `/candidates` | Capitalization candidates from AP/expense |
| POST | `/candidates/{id}/convert` | Convert candidate → draft asset |
| GET | `/categories/list` | Asset categories |
| POST | `/ai/suggest` | AI category/useful-life suggestion stub |

## Accounting

**Capitalization:**
| Account | Debit | Credit |
|---------|-------|--------|
| Fixed Asset | cost | |
| Expense / Bank (reclass) | | cost |

**Depreciation (monthly):**
| Account | Debit | Credit |
|---------|-------|--------|
| Depreciation Expense | amount | |
| Accumulated Depreciation | | amount |

**Disposal:** Dr Bank, Dr Accumulated Depreciation, Dr/Cr Gain/Loss, Cr Fixed Asset

## Workflows
- `ASSET_CAPITALIZATION_APPROVAL`, `ASSET_DISPOSAL_APPROVAL`, `ASSET_IMPAIRMENT_APPROVAL`

## Events (`source=erp.assets`)
- Emitted: `asset.created`, `asset.capitalized`, `asset.depreciated`, `asset.transferred`, `asset.impaired`, `asset.disposed`, `asset.candidate.detected`
- Consumed: `invoice.approved` (candidates), `expense.claim.approved` (candidates), workflow approvals
- Scheduler: `scheduler.tick` → `depreciation_service.run_due`

## Integrations
- **M13 AP:** `line_type=fixed_asset` routes to fixed asset account at approve; invoice approved creates capitalization candidate when above threshold
- **M16 Expenses:** Approved claims above threshold create candidates
- **M15 Procurement:** PO lines with fixed asset `expense_account_id` (future candidate hook via AP)
- **M31 Reporting:** Register API + event payloads for FA register, depreciation schedule, movement

## Blueprint compliance

| Requirement | Status |
|-------------|--------|
| Asset categories + policies | ✅ |
| Asset register | ✅ |
| Straight-line depreciation | ✅ |
| Monthly scheduler batch | ✅ |
| Capitalization threshold | ✅ |
| Transfer (no GL) | ✅ |
| Impairment | ✅ |
| Disposal gain/loss | ✅ |
| AP/expense acquisition candidates | ✅ |
| Workflows + events + IAM | ✅ |
| IND-AS extensible (`depreciation_method` enum) | ✅ |
