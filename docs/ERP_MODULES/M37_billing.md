# M37 — Billing, Subscription & Usage Governance

M37 is the **commercial control layer** for org-level subscriptions, feature entitlements, usage quotas, and AI credits. It gates access before IAM and M34 on all ERP and Finance OS paths.

## Golden rule

Never hardcode plan checks (`if plan == "growth"`) in business modules. Always call `billing_guard.check(...)` or `enforce_billing(org_id, feature)` from module guards.

## Persistence

Migration `065_billing_engine.sql`:

- `billing.plans`, `billing.plan_features`, `billing.plan_limits`
- `billing.org_subscriptions`, `billing.org_entitlements`
- `billing.org_credit_wallets`, `billing.credit_transactions`
- `billing.ai_usage` (internal token/cost — not customer-facing)
- `billing.usage_metrics`, `billing.usage_events`

Bootstrap: `python backend/scripts/bootstrap_billing_plans.py --org-id <uuid> [--plan-key finance_starter]`

New orgs: `POST /organizations` auto-assigns `finance_starter` and seeds credit wallet.

## Plans (v1)

| Plan key | AI credits/mo |
|----------|---------------|
| `finance_starter` | 0 |
| `finance_growth` | 500 |
| `finance_os_pro` | 2000 |
| `enterprise` | configurable |

Payments: internal plan assignment only in v1 (no Razorpay/Stripe).

## Services

| Service | Role |
|---------|------|
| `plan_service` | Plan catalog and limits |
| `subscription_service` | Org plan assignment |
| `entitlement_service` | `has_feature`, overrides |
| `usage_service` | Quotas and metering |
| `credit_service` | AI credit wallet |
| `billing_guard` | Unified commercial gate |

## HTTP API

Customer (`/api/v1/billing/*`):

- `GET /billing/subscription`
- `GET /billing/entitlements`
- `GET /billing/usage`
- `GET /billing/credits`
- `GET /billing/plans`

Admin (`/api/v1/admin/billing/*`, requires `platform.admin` — platform owner only, not customer `tenant_admin`):

- `GET /admin/billing/plans`
- `POST /admin/billing/subscriptions/assign`
- `POST /admin/billing/credits/grant`
- `POST /admin/billing/entitlements/override`

## Integration

- ERP guards M8–M24, M31, M35: `enforce_billing` in `security/*_guard.py`
- Finance OS M25–M30, M32, M33: feature codes per module
- M36 API Gateway: `api_platform` feature + API call quotas
- Pipelines M25–M30: `billing_ai_operation` reserve/commit
- `event_consumers.py`: `gate_ai_event` before async pipeline runs
- `llm_provider.py`: token logging + credit deduction on LLM calls

## Layer order

```
Request → M37 (entitlement/quota/credits) → IAM → M34 → business logic → meter/deduct
```
