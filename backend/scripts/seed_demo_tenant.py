"""Seed a known-good Flora Demo ERP tenant with rich transactional data for AI/UI testing.

Creates a dedicated organization (not the benchmark org) with:
  - Company / branch / users / roles
  - Chart of accounts, fiscal year + open periods
  - GST registration + tax rates
  - Vendors (ACME, Infosys, ABC Supplies, …) and customers
  - Bank accounts + unreconciled / matched transactions
  - Purchase orders + GRNs
  - AP invoices (draft / unpaid / overdue / paid / duplicates)
  - AR invoices + receipts
  - AP payments + allocations
  - Journals and GST transaction rows
  - Billing subscription + sample KPI snapshots

Usage:
  python backend/scripts/seed_demo_tenant.py
  python backend/scripts/seed_demo_tenant.py --dsn postgresql://...
  python backend/scripts/seed_demo_tenant.py --password 'YourPass1'

Login (after seed):
  email:    demo.admin@flora.demo
  password: Demo@Tenant1
  org_id:   33333333-3333-4333-8333-333333333333
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
from argon2 import PasswordHasher
from psycopg.types.json import Json

# ---------------------------------------------------------------------------
# Fixed IDs (RFC4122-looking, stable across re-runs)
# ---------------------------------------------------------------------------
ORG_ID = "33333333-3333-4333-8333-333333333333"
COMPANY_ID = "c3330001-0001-4001-8001-000000000001"
BRANCH_ID = "d3330001-0001-4001-8001-000000000001"

ADMIN_USER_ID = "a3330001-0001-4001-8001-000000000001"
AP_USER_ID = "a3330001-0001-4001-8001-000000000002"
AR_USER_ID = "a3330001-0001-4001-8001-000000000003"

DEFAULT_EMAIL = "demo.admin@flora.demo"
DEFAULT_PASSWORD = "Demo@Tenant1"
AP_EMAIL = "demo.ap@flora.demo"
AR_EMAIL = "demo.ar@flora.demo"
ORG_NAME = "Flora Demo Trading Pvt Ltd"
ORG_SLUG = "flora-demo-trading"
COMPANY_NAME = "Flora Demo Trading Pvt Ltd"
GSTIN = "29AABCF1234D1Z5"
PAN = "AABCF1234D"

FY_ID = "f3330001-0001-4001-8001-000000000001"

# Role IDs for this org (mirror benchmark role set)
ROLE_IDS = {
    "tenant_admin": "b3330001-0001-4001-8001-000000000001",
    "cfo": "b3330001-0001-4001-8001-000000000002",
    "controller": "b3330001-0001-4001-8001-000000000003",
    "ap_manager": "b3330001-0001-4001-8001-000000000004",
    "ap_executive": "b3330001-0001-4001-8001-000000000005",
    "ap_preparer": "b3330001-0001-4001-8001-000000000006",
    "ar_manager": "b3330001-0001-4001-8001-000000000007",
    "auditor": "b3330001-0001-4001-8001-000000000008",
    "analyst": "b3330001-0001-4001-8001-000000000009",
    "governance_admin": "b3330001-0001-4001-8001-00000000000a",
}

# Deterministic entity IDs
def _uid(suffix: str) -> str:
    """Build uuid: e3330001-0001-4001-8001-############ (12 hex chars)."""
    h = hashlib.md5(suffix.encode()).hexdigest()[:12]
    return f"e3330001-0001-4001-8001-{h}"


VENDOR_IDS = {
    "ACME": _uid("vendor:acme"),
    "INFY": _uid("vendor:infosys"),
    "ABC": _uid("vendor:abc"),
    "TCS": _uid("vendor:tcs"),
    "LOCAL": _uid("vendor:local"),
}
CUSTOMER_IDS = {
    "RELIANCE": _uid("customer:reliance"),
    "WIPRO": _uid("customer:wipro"),
    "RETAIL1": _uid("customer:retail1"),
    "GOV1": _uid("customer:gov1"),
}

# COA
GROUP_IDS = {k: _uid(f"grp:{k}") for k in ("assets", "liabilities", "equity", "revenue", "expense")}
ACCT = {
    "cash": _uid("acct:cash"),
    "bank": _uid("acct:bank"),
    "ar": _uid("acct:ar"),
    "ap": _uid("acct:ap"),
    "gst_input": _uid("acct:gst_input"),
    "gst_output": _uid("acct:gst_output"),
    "revenue": _uid("acct:revenue"),
    "cogs": _uid("acct:cogs"),
    "expense_ops": _uid("acct:expense_ops"),
    "expense_it": _uid("acct:expense_it"),
    "equity": _uid("acct:equity"),
}

BANK_ID = _uid("bank:hdfc-ops")
BANK_LEDGER = ACCT["bank"]

PO_IDS = {
    "PO-ACME-001": _uid("po:acme001"),
    "PO-INFY-001": _uid("po:infy001"),
    "PO-ABC-001": _uid("po:abc001"),
}

# AP invoice numbers used in AI prompts
AP_INV = {
    "INV-001": _uid("ap:inv001"),
    "INV-002": _uid("ap:inv002"),
    "INV-003": _uid("ap:inv003"),
    "INV-004": _uid("ap:inv004"),
    "INV-005": _uid("ap:inv005"),
    "INV-006": _uid("ap:inv006"),
    "INV-006B": _uid("ap:inv006b"),
    "INV-007": _uid("ap:inv007"),
    "INV-008": _uid("ap:inv008"),
    "INV-009": _uid("ap:inv009"),
    "INV-010": _uid("ap:inv010"),
}


def _load_dsn_from_env() -> str | None:
    env_path = Path(__file__).resolve().parents[1] / "apps" / "api" / ".env"
    if not env_path.exists():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "POSTGRES_DSN":
            return value.strip().strip('"').strip("'")
    return None


def _set_org(cur, org_id: str) -> None:
    cur.execute("SELECT set_config('app.current_org', %s, true)", (org_id,))


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, table),
    )
    return bool(cur.fetchone()[0])


def _dec(n: float | int | str) -> Decimal:
    return Decimal(str(n))


def _dup_checksum(*parts: str) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Seed sections
# ---------------------------------------------------------------------------


def seed_org_and_company(cur) -> None:
    _set_org(cur, ORG_ID)
    cur.execute(
        """
        INSERT INTO core.organizations (
          id, name, plan, slug, status, country_code, timezone, currency
        ) VALUES (
          %s::uuid, %s, 'enterprise', %s, 'active', 'IN', 'Asia/Kolkata', 'INR'
        )
        ON CONFLICT (id) DO UPDATE SET
          name = EXCLUDED.name,
          plan = EXCLUDED.plan,
          slug = EXCLUDED.slug,
          status = 'active',
          updated_at = NOW()
        """,
        (ORG_ID, ORG_NAME, ORG_SLUG),
    )
    cur.execute(
        """
        INSERT INTO core.companies (
          id, org_id, legal_name, gstin, pan, base_currency, financial_year_start, status
        ) VALUES (
          %s::uuid, %s::uuid, %s, %s, %s, 'INR', '2026-04-01'::date, 'active'
        )
        ON CONFLICT (id) DO UPDATE SET
          legal_name = EXCLUDED.legal_name,
          gstin = EXCLUDED.gstin,
          pan = EXCLUDED.pan,
          status = 'active',
          updated_at = NOW()
        """,
        (COMPANY_ID, ORG_ID, COMPANY_NAME, GSTIN, PAN),
    )
    cur.execute(
        """
        INSERT INTO core.branches (
          id, company_id, org_id, branch_code, branch_name, state_code, address
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, 'HQ', 'Bengaluru HQ', '29',
          %s::jsonb
        )
        ON CONFLICT (id) DO UPDATE SET
          branch_name = EXCLUDED.branch_name,
          state_code = EXCLUDED.state_code,
          updated_at = NOW()
        """,
        (
            BRANCH_ID,
            COMPANY_ID,
            ORG_ID,
            json.dumps({"city": "Bengaluru", "line1": "100 MG Road", "pincode": "560001"}),
        ),
    )


def seed_roles_and_users(cur, password: str) -> None:
    _set_org(cur, ORG_ID)
    role_defs = [
        ("tenant_admin", "Full tenant administrator", True, {"max_approve_amount": None}),
        ("cfo", "Chief Financial Officer", True, {"max_approve_amount": None, "mfa_required": True}),
        ("controller", "Financial controller", True, {"max_approve_amount": None}),
        ("ap_manager", "Accounts payable manager", True, {"max_approve_amount": 1000000}),
        ("ap_executive", "Accounts payable executive", True, {"max_approve_amount": 500000}),
        ("ap_preparer", "AP preparer", True, {"max_approve_amount": 0, "disallowed_actions": ["approve_payment"]}),
        ("ar_manager", "Accounts receivable manager", True, {}),
        ("auditor", "Read-only auditor", True, {"read_only": True}),
        ("analyst", "Finance analyst", True, {"max_approve_amount": 0}),
        ("governance_admin", "Governance and payroll access", True, {}),
    ]
    for name, desc, system, policy in role_defs:
        cur.execute(
            """
            INSERT INTO core.roles (id, org_id, name, description, system_role, policy_context)
            VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
              description = EXCLUDED.description,
              policy_context = EXCLUDED.policy_context
            """,
            (ROLE_IDS[name], ORG_ID, name, desc, system, json.dumps(policy)),
        )

    # Broad permissions for admin-like roles
    cur.execute(
        """
        INSERT INTO core.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM core.roles r
        CROSS JOIN core.permissions p
        WHERE r.org_id = %s::uuid
          AND r.name IN ('tenant_admin', 'cfo', 'controller')
        ON CONFLICT DO NOTHING
        """,
        (ORG_ID,),
    )
    # AP manager subset (best-effort by key; ignore missing keys)
    cur.execute(
        """
        INSERT INTO core.role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM core.roles r
        JOIN core.permissions p ON TRUE
        WHERE r.org_id = %s::uuid AND r.name IN ('ap_manager', 'ap_executive', 'ar_manager', 'analyst')
        ON CONFLICT DO NOTHING
        """,
        (ORG_ID,),
    )

    hasher = PasswordHasher()
    pwd_hash = hasher.hash(password)
    users = [
        (ADMIN_USER_ID, DEFAULT_EMAIL, "Flora Demo Admin"),
        (AP_USER_ID, AP_EMAIL, "Flora Demo AP Clerk"),
        (AR_USER_ID, AR_EMAIL, "Flora Demo AR Clerk"),
    ]
    for uid, email, display in users:
        cur.execute(
            """
            INSERT INTO core.users (id, org_id, email, display_name, status, password_hash, mfa_enabled)
            VALUES (%s::uuid, %s::uuid, %s, %s, 'active', %s, FALSE)
            ON CONFLICT (id) DO UPDATE SET
              email = EXCLUDED.email,
              display_name = EXCLUDED.display_name,
              status = 'active',
              password_hash = EXCLUDED.password_hash,
              mfa_enabled = FALSE,
              updated_at = NOW()
            """,
            (uid, ORG_ID, email, display, pwd_hash),
        )

    # Admin: all roles except auditor + ap_preparer (avoids ABAC approve_payment strip)
    for name, rid in ROLE_IDS.items():
        if name in ("auditor", "ap_preparer"):
            continue
        cur.execute(
            """
            INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
            ON CONFLICT (user_id, role_id) DO UPDATE SET
              company_id = EXCLUDED.company_id,
              branch_id = EXCLUDED.branch_id
            """,
            (ORG_ID, ADMIN_USER_ID, rid, COMPANY_ID, BRANCH_ID),
        )
    # AP user
    for name in ("ap_manager", "ap_executive"):
        cur.execute(
            """
            INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """,
            (ORG_ID, AP_USER_ID, ROLE_IDS[name], COMPANY_ID, BRANCH_ID),
        )
    # AR user
    cur.execute(
        """
        INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
        ON CONFLICT (user_id, role_id) DO NOTHING
        """,
        (ORG_ID, AR_USER_ID, ROLE_IDS["ar_manager"], COMPANY_ID, BRANCH_ID),
    )


def seed_coa(cur) -> None:
    _set_org(cur, ORG_ID)
    groups = [
        (GROUP_IDS["assets"], "Assets", "ASSETS", "asset", "debit"),
        (GROUP_IDS["liabilities"], "Liabilities", "LIAB", "liability", "credit"),
        (GROUP_IDS["equity"], "Equity", "EQUITY", "equity", "credit"),
        (GROUP_IDS["revenue"], "Revenue", "REV", "revenue", "credit"),
        (GROUP_IDS["expense"], "Expenses", "EXP", "expense", "debit"),
    ]
    for gid, name, code, gtype, nature in groups:
        cur.execute(
            """
            INSERT INTO erp.account_groups (
              id, org_id, company_id, group_name, group_code, group_type, nature
            ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET group_name = EXCLUDED.group_name
            """,
            (gid, ORG_ID, COMPANY_ID, name, code, gtype, nature),
        )

    accounts = [
        (ACCT["cash"], "1000", "Cash on Hand", "asset", GROUP_IDS["assets"]),
        (ACCT["bank"], "1010", "HDFC Operating Bank", "asset", GROUP_IDS["assets"]),
        (ACCT["ar"], "1100", "Accounts Receivable", "asset", GROUP_IDS["assets"]),
        (ACCT["gst_input"], "1200", "GST Input Credit", "asset", GROUP_IDS["assets"]),
        (ACCT["ap"], "2000", "Accounts Payable", "liability", GROUP_IDS["liabilities"]),
        (ACCT["gst_output"], "2100", "GST Output Liability", "liability", GROUP_IDS["liabilities"]),
        (ACCT["equity"], "3000", "Share Capital", "equity", GROUP_IDS["equity"]),
        (ACCT["revenue"], "4000", "Sales Revenue", "revenue", GROUP_IDS["revenue"]),
        (ACCT["cogs"], "5000", "Cost of Goods Sold", "expense", GROUP_IDS["expense"]),
        (ACCT["expense_ops"], "5100", "Operating Expenses", "expense", GROUP_IDS["expense"]),
        (ACCT["expense_it"], "5200", "IT / Professional Services", "expense", GROUP_IDS["expense"]),
    ]
    for aid, code, name, atype, gid in accounts:
        cur.execute(
            """
            INSERT INTO erp.chart_of_accounts (
              id, org_id, company_id, account_code, account_name, account_type, group_id, is_postable, is_active
            ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s::uuid, TRUE, TRUE)
            ON CONFLICT (id) DO UPDATE SET
              account_name = EXCLUDED.account_name,
              is_active = TRUE,
              updated_at = NOW()
            """,
            (aid, ORG_ID, COMPANY_ID, code, name, atype, gid),
        )


def seed_fiscal(cur, today: date) -> dict[str, str]:
    """Create FY spanning today (Indian FY Apr–Mar) and monthly periods. Return period_id by YYYY-MM."""
    _set_org(cur, ORG_ID)
    if today.month >= 4:
        fy_start = date(today.year, 4, 1)
        fy_end = date(today.year + 1, 3, 31)
        fy_code = f"FY{today.year}-{str(today.year + 1)[-2:]}"
    else:
        fy_start = date(today.year - 1, 4, 1)
        fy_end = date(today.year, 3, 31)
        fy_code = f"FY{today.year - 1}-{str(today.year)[-2:]}"

    cur.execute(
        """
        INSERT INTO erp.fiscal_years (
          id, org_id, company_id, fiscal_year_code, start_date, end_date, status, is_current
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date, 'open', TRUE
        )
        ON CONFLICT (org_id, fiscal_year_code) DO UPDATE SET
          is_current = TRUE,
          status = 'open',
          updated_at = NOW()
        RETURNING id::text
        """,
        (FY_ID, ORG_ID, COMPANY_ID, fy_code, fy_start.isoformat(), fy_end.isoformat()),
    )
    row = cur.fetchone()
    fy_id = row[0] if row else FY_ID

    # Unset other current years for this org
    cur.execute(
        """
        UPDATE erp.fiscal_years SET is_current = FALSE, updated_at = NOW()
        WHERE org_id = %s::uuid AND id <> %s::uuid
        """,
        (ORG_ID, fy_id),
    )

    period_ids: dict[str, str] = {}
    # 12 months from fy_start
    cursor = fy_start
    for n in range(1, 13):
        if cursor.month == 12:
            pend = date(cursor.year, 12, 31)
            next_start = date(cursor.year + 1, 1, 1)
        else:
            next_start = date(cursor.year, cursor.month + 1, 1)
            pend = next_start - timedelta(days=1)
        pid = _uid(f"fp:{fy_code}:{n:02d}")
        pname = cursor.strftime("%b %Y")
        key = cursor.strftime("%Y-%m")
        cur.execute(
            """
            INSERT INTO erp.fiscal_periods (
              id, org_id, company_id, period_name, start_date, end_date, status, is_locked,
              fiscal_year_id, period_number, lock_status
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date, 'open', FALSE,
              %s::uuid, %s, 'open'
            )
            ON CONFLICT (id) DO UPDATE SET
              status = 'open',
              is_locked = FALSE,
              lock_status = 'open'
            """,
            (pid, ORG_ID, COMPANY_ID, pname, cursor.isoformat(), pend.isoformat(), fy_id, n),
        )
        period_ids[key] = pid
        cursor = next_start
    return period_ids


def seed_tax(cur) -> None:
    _set_org(cur, ORG_ID)
    if _table_exists(cur, "erp", "gst_registrations"):
        cur.execute(
            """
            INSERT INTO erp.gst_registrations (
              id, org_id, company_id, gstin, legal_name, trade_name, state_code, registration_type, status
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, '29', 'regular', 'active'
            )
            ON CONFLICT (org_id, gstin) DO UPDATE SET
              legal_name = EXCLUDED.legal_name,
              status = 'active',
              updated_at = NOW()
            """,
            (_uid("gst:reg"), ORG_ID, COMPANY_ID, GSTIN, COMPANY_NAME, "Flora Demo"),
        )
    if _table_exists(cur, "erp", "tax_rate_master"):
        rates = [(0, "Zero rated"), (5, "GST 5%"), (12, "GST 12%"), (18, "GST 18%"), (28, "GST 28%")]
        for rate, desc in rates:
            cur.execute(
                """
                INSERT INTO erp.tax_rate_master (id, org_id, hsn_sac, description, gst_rate)
                VALUES (%s::uuid, %s::uuid, NULL, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (_uid(f"taxrate:{rate}"), ORG_ID, desc, rate),
            )


def seed_parties(cur) -> None:
    _set_org(cur, ORG_ID)
    vendors = [
        ("ACME", "V-ACME", "ACME", "29AACCA1234A1Z5", "AACCA1234A", "ap@acme.example", 30),
        ("INFY", "V-INFY", "Infosys", "29AAACI1234A1Z8", "AAACI1234A", "ap@infosys.example", 45),
        ("ABC", "V-ABC", "ABC Supplies", "29AABCA1234A1Z1", "AABCA1234A", "billing@abc.example", 15),
        ("TCS", "V-TCS", "Tata Consultancy Services", "27AAACT1234A1Z9", "AAACT1234A", "ap@tcs.example", 30),
        ("LOCAL", "V-LOCAL", "Local Stationery Mart", None, None, "shop@local.example", 7),
    ]
    for key, code, name, gstin, pan, email, terms in vendors:
        cur.execute(
            """
            INSERT INTO erp.vendors (
              id, org_id, company_id, vendor_code, vendor_name, gstin, pan, email,
              payment_terms_days, status, payable_account_id, created_by
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, 'active', %s::uuid, %s::uuid
            )
            ON CONFLICT (id) DO UPDATE SET
              vendor_name = EXCLUDED.vendor_name,
              status = 'active',
              updated_at = NOW()
            """,
            (
                VENDOR_IDS[key],
                ORG_ID,
                COMPANY_ID,
                code,
                name,
                gstin,
                pan,
                email,
                terms,
                ACCT["ap"],
                ADMIN_USER_ID,
            ),
        )
        cur.execute(
            """
            INSERT INTO erp.vendor_bank_accounts (
              id, org_id, vendor_id, account_number_encrypted, ifsc_code, bank_name, is_primary, verified
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, TRUE, TRUE
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (
                _uid(f"vba:{key}"),
                ORG_ID,
                VENDOR_IDS[key],
                f"enc:demo-{code}-1234567890",
                "HDFC0001234",
                "HDFC Bank",
            ),
        )

    customers = [
        ("RELIANCE", "C-REL", "Reliance Retail Ltd", "corporate", "27AABCR1234A1Z2", 5000000, 30),
        ("WIPRO", "C-WIP", "Wipro Limited", "corporate", "29AAACW1234A1Z7", 2000000, 45),
        ("RETAIL1", "C-RET1", "Corner Shoppe", "retail", None, 50000, 7),
        ("GOV1", "C-GOV1", "Karnataka State Dept", "government", "29AAAAK1234A1ZD", 10000000, 60),
    ]
    for key, code, name, ctype, gstin, limit_, terms in customers:
        cur.execute(
            """
            INSERT INTO erp.customers (
              id, org_id, company_id, customer_code, customer_name, customer_type, gstin,
              credit_limit, payment_terms_days, receivable_account_id, revenue_account_id,
              status, created_by
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid, 'active', %s::uuid
            )
            ON CONFLICT (id) DO UPDATE SET
              customer_name = EXCLUDED.customer_name,
              status = 'active',
              updated_at = NOW()
            """,
            (
                CUSTOMER_IDS[key],
                ORG_ID,
                COMPANY_ID,
                code,
                name,
                ctype,
                gstin,
                limit_,
                terms,
                ACCT["ar"],
                ACCT["revenue"],
                ADMIN_USER_ID,
            ),
        )


def seed_banking(cur, today: date) -> None:
    _set_org(cur, ORG_ID)
    cur.execute(
        """
        INSERT INTO erp.bank_accounts (
          id, org_id, company_id, account_name, bank_name, account_number_encrypted, ifsc_code,
          currency_code, account_type, ledger_account_id, is_active, opening_balance, created_by
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, 'HDFC Current - Ops', 'HDFC Bank', 'enc:demo-ops-9988776655',
          'HDFC0001987', 'INR', 'current', %s::uuid, TRUE, 2500000.00, %s::uuid
        )
        ON CONFLICT (id) DO UPDATE SET
          is_active = TRUE,
          opening_balance = EXCLUDED.opening_balance,
          updated_at = NOW()
        """,
        (BANK_ID, ORG_ID, COMPANY_ID, BANK_LEDGER, ADMIN_USER_ID),
    )
    # Bank feed lines for reconcile scenarios
    txns = [
        (_uid("btxn:1"), today - timedelta(days=2), 118000.00, "debit", "unreconciled", "NEFT to ACME INV-001"),
        (_uid("btxn:2"), today - timedelta(days=5), 250000.00, "credit", "unreconciled", "Receipt Reliance AR-001"),
        (_uid("btxn:3"), today - timedelta(days=10), 54000.00, "debit", "matched", "Payment ABC INV-005"),
        (_uid("btxn:4"), today - timedelta(days=1), 999.00, "debit", "exception", "Unknown UPI charge"),
        (_uid("btxn:5"), today - timedelta(days=3), 175000.00, "credit", "suggested", "Wipro remittance"),
    ]
    for tid, tdate, amount, ttype, recon, desc in txns:
        cur.execute(
            """
            INSERT INTO erp.bank_transactions (
              id, org_id, bank_account_id, transaction_reference, transaction_date, amount,
              transaction_type, description, source, reconciliation_status, import_idempotency_key
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s, %s, %s, 'manual_import', %s, %s
            )
            ON CONFLICT (id) DO UPDATE SET
              reconciliation_status = EXCLUDED.reconciliation_status,
              description = EXCLUDED.description,
              updated_at = NOW()
            """,
            (
                tid,
                ORG_ID,
                BANK_ID,
                f"BNK-{tid[-6:]}",
                tdate.isoformat(),
                amount,
                ttype,
                desc,
                recon,
                f"demo-import-{tid}",
            ),
        )


def seed_procurement(cur, today: date) -> None:
    _set_org(cur, ORG_ID)
    pos = [
        ("PO-ACME-001", "ACME", "approved", 100000.00, 18000.00, 118000.00),
        ("PO-INFY-001", "INFY", "sent", 200000.00, 36000.00, 236000.00),
        ("PO-ABC-001", "ABC", "partially_received", 50000.00, 9000.00, 59000.00),
    ]
    for po_num, vkey, status, sub, gst, total in pos:
        pid = PO_IDS[po_num]
        cur.execute(
            """
            INSERT INTO erp.purchase_orders (
              id, org_id, company_id, po_number, vendor_id, status, workflow_approved,
              po_date, expected_delivery_date, subtotal, gst_amount, total_amount, created_by, approved_by
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s, TRUE,
              %s::date, %s::date, %s, %s, %s, %s::uuid, %s::uuid
            )
            ON CONFLICT (org_id, po_number) DO UPDATE SET
              status = EXCLUDED.status,
              total_amount = EXCLUDED.total_amount,
              updated_at = NOW()
            """,
            (
                pid,
                ORG_ID,
                COMPANY_ID,
                po_num,
                VENDOR_IDS[vkey],
                status,
                (today - timedelta(days=20)).isoformat(),
                (today + timedelta(days=10)).isoformat(),
                sub,
                gst,
                total,
                ADMIN_USER_ID,
                ADMIN_USER_ID,
            ),
        )
        cur.execute(
            """
            INSERT INTO erp.purchase_order_items (
              id, org_id, po_id, item_name, quantity, received_quantity, unit_price, amount, hsn_sac
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s, 1, %s, %s, %s, '998314'
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (
                _uid(f"poi:{po_num}"),
                ORG_ID,
                pid,
                f"Services / goods for {po_num}",
                1 if status == "partially_received" else 0,
                sub,
                sub,
            ),
        )
    # GRN for ABC
    cur.execute(
        """
        INSERT INTO erp.goods_receipts (
          id, org_id, grn_number, po_id, received_by, received_date, status, workflow_approved
        ) VALUES (
          %s::uuid, %s::uuid, 'GRN-ABC-001', %s::uuid, %s::uuid, %s::date, 'confirmed', TRUE
        )
        ON CONFLICT (org_id, grn_number) DO UPDATE SET status = 'confirmed', updated_at = NOW()
        """,
        (_uid("grn:abc001"), ORG_ID, PO_IDS["PO-ABC-001"], ADMIN_USER_ID, (today - timedelta(days=7)).isoformat()),
    )


def _insert_ap_invoice(
    cur,
    *,
    iid: str,
    number: str,
    vendor_key: str,
    inv_date: date,
    due_date: date,
    amount: float,
    gst: float,
    status: str,
    paid: float = 0.0,
    checksum: str | None = None,
    po_id: str | None = None,
    description: str = "",
) -> None:
    total = amount + gst
    cur.execute(
        """
        INSERT INTO erp.ap_invoices (
          id, org_id, company_id, branch_id, vendor_id, invoice_number, invoice_date, due_date,
          invoice_amount, gst_amount, total_amount, paid_amount, status, duplicate_checksum,
          purchase_order_id, created_by, approved_by, metadata
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date,
          %s, %s, %s, %s, %s, %s, %s::uuid, %s::uuid, %s::uuid, %s::jsonb
        )
        ON CONFLICT (id) DO UPDATE SET
          status = EXCLUDED.status,
          paid_amount = EXCLUDED.paid_amount,
          due_date = EXCLUDED.due_date,
          total_amount = EXCLUDED.total_amount,
          updated_at = NOW()
        """,
        (
            iid,
            ORG_ID,
            COMPANY_ID,
            BRANCH_ID,
            VENDOR_IDS[vendor_key],
            number,
            inv_date.isoformat(),
            due_date.isoformat(),
            amount,
            gst,
            total,
            paid,
            status,
            checksum,
            po_id,
            ADMIN_USER_ID,
            ADMIN_USER_ID if status in ("approved", "partially_paid", "paid") else None,
            json.dumps({"seed": "demo_tenant", "note": description}),
        ),
    )
    cur.execute(
        """
        INSERT INTO erp.ap_invoice_lines (
          id, org_id, invoice_id, account_id, line_type, description, amount, tax_code
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'expense', %s, %s, 'GST18'
        )
        ON CONFLICT (id) DO NOTHING
        """,
        (_uid(f"apline:{number}"), ORG_ID, iid, ACCT["expense_ops"], description or number, amount),
    )


def seed_ap(cur, today: date) -> None:
    _set_org(cur, ORG_ID)
    # INV-001: ACME approved unpaid — "Why hasn't INV-001 been paid?" / unpaid list
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-001"],
        number="INV-001",
        vendor_key="ACME",
        inv_date=today - timedelta(days=25),
        due_date=today - timedelta(days=5),
        amount=100000,
        gst=18000,
        status="approved",
        po_id=PO_IDS["PO-ACME-001"],
        description="ACME annual SaaS — awaiting payment",
    )
    # INV-002: draft — "Create / submit" style workflow
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-002"],
        number="INV-002",
        vendor_key="ACME",
        inv_date=today,
        due_date=today + timedelta(days=30),
        amount=25000,
        gst=4500,
        status="draft",
        description="ACME add-on services draft",
    )
    # INV-003: Infosys approved unpaid this month
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-003"],
        number="INV-003",
        vendor_key="INFY",
        inv_date=today - timedelta(days=3),
        due_date=today + timedelta(days=42),
        amount=200000,
        gst=36000,
        status="approved",
        po_id=PO_IDS["PO-INFY-001"],
        description="Infosys consulting Aug-Sep",
    )
    # INV-004: overdue ABC
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-004"],
        number="INV-004",
        vendor_key="ABC",
        inv_date=today - timedelta(days=60),
        due_date=today - timedelta(days=30),
        amount=45000,
        gst=8100,
        status="approved",
        description="ABC Supplies overdue stationery",
    )
    # INV-005: paid
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-005"],
        number="INV-005",
        vendor_key="ABC",
        inv_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        amount=45762.71,
        gst=8237.29,
        status="paid",
        paid=54000,
        po_id=PO_IDS["PO-ABC-001"],
        description="ABC paid invoice",
    )
    # Near-duplicate pair for "Find duplicate invoices".
    # Unique index uq_erp_ap_invoices_duplicate blocks identical checksums, so we
    # share a demo group in metadata and leave checksums distinct.
    dup_base = _dup_checksum("ACME", "75000", "13500", (today - timedelta(days=8)).isoformat())
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-006"],
        number="INV-006",
        vendor_key="ACME",
        inv_date=today - timedelta(days=8),
        due_date=today + timedelta(days=22),
        amount=75000,
        gst=13500,
        status="pending_review",
        checksum=f"{dup_base}:a",
        description="Possible duplicate A | group=DUP-ACME-75K",
    )
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-006B"],
        number="INV-006-DUP",
        vendor_key="ACME",
        inv_date=today - timedelta(days=7),
        due_date=today + timedelta(days=23),
        amount=75000,
        gst=13500,
        status="pending_review",
        checksum=f"{dup_base}:b",
        description="Possible duplicate B | group=DUP-ACME-75K",
    )
    # pending approval
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-007"],
        number="INV-007",
        vendor_key="TCS",
        inv_date=today - timedelta(days=2),
        due_date=today + timedelta(days=28),
        amount=150000,
        gst=27000,
        status="pending_approval",
        description="TCS support pending approval",
    )
    # partially paid
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-008"],
        number="INV-008",
        vendor_key="LOCAL",
        inv_date=today - timedelta(days=15),
        due_date=today + timedelta(days=5),
        amount=10000,
        gst=1800,
        status="partially_paid",
        paid=5000,
        description="Local stationery partial",
    )
    # more this-month invoices
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-009"],
        number="INV-009",
        vendor_key="INFY",
        inv_date=today - timedelta(days=1),
        due_date=today + timedelta(days=44),
        amount=80000,
        gst=14400,
        status="approved",
        description="Infosys this-month SOW",
    )
    _insert_ap_invoice(
        cur,
        iid=AP_INV["INV-010"],
        number="INV-010",
        vendor_key="ACME",
        inv_date=today,
        due_date=today + timedelta(days=30),
        amount=12000,
        gst=2160,
        status="approved",
        description="ACME consumables this month",
    )

    # Vendor balances (outstanding)
    balances = {
        "ACME": 100000 + 18000 + 75000 + 13500 + 75000 + 13500 + 12000 + 2160,  # approx unpaid
        "INFY": 200000 + 36000 + 80000 + 14400,
        "ABC": 45000 + 8100,
        "TCS": 150000 + 27000,
        "LOCAL": 11800 - 5000,
    }
    # Recompute more accurately from statuses we care about
    outstanding = {
        "ACME": (118000 - 0) + (88500) + (88500) + (14160),  # INV-001 + 006 + 006B + 010 (006 pending still outstanding)
        "INFY": 236000 + 94400,
        "ABC": 53100,
        "TCS": 177000,
        "LOCAL": 6800,
    }
    for key, amt in outstanding.items():
        cur.execute(
            """
            INSERT INTO erp.vendor_balances (id, org_id, vendor_id, outstanding_amount)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s)
            ON CONFLICT (org_id, vendor_id) DO UPDATE SET
              outstanding_amount = EXCLUDED.outstanding_amount,
              last_updated = NOW()
            """,
            (_uid(f"vbal:{key}"), ORG_ID, VENDOR_IDS[key], amt),
        )

    # Payment for INV-005
    pay_id = _uid("pay:abc005")
    cur.execute(
        """
        INSERT INTO erp.ap_payments (
          id, org_id, company_id, vendor_id, payment_reference, payment_date, amount,
          status, bank_account_id, created_by
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'PAY-ABC-005', %s::date, 54000,
          'completed', %s::uuid, %s::uuid
        )
        ON CONFLICT (org_id, payment_reference) DO UPDATE SET
          status = 'completed',
          amount = EXCLUDED.amount,
          updated_at = NOW()
        """,
        (pay_id, ORG_ID, COMPANY_ID, VENDOR_IDS["ABC"], (today - timedelta(days=10)).isoformat(), BANK_ID, ADMIN_USER_ID),
    )
    # Resolve payment id after upsert
    cur.execute(
        "SELECT id::text FROM erp.ap_payments WHERE org_id=%s::uuid AND payment_reference='PAY-ABC-005'",
        (ORG_ID,),
    )
    pay_row = cur.fetchone()
    pay_id = pay_row[0] if pay_row else pay_id
    cur.execute(
        """
        INSERT INTO erp.ap_payment_allocations (id, org_id, payment_id, invoice_id, amount)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 54000)
        ON CONFLICT (id) DO NOTHING
        """,
        (_uid("payalloc:abc005"), ORG_ID, pay_id, AP_INV["INV-005"]),
    )
    # Partial payment LOCAL
    pay2 = _uid("pay:local008")
    cur.execute(
        """
        INSERT INTO erp.ap_payments (
          id, org_id, company_id, vendor_id, payment_reference, payment_date, amount,
          status, bank_account_id, created_by
        ) VALUES (
          %s::uuid, %s::uuid, %s::uuid, %s::uuid, 'PAY-LOCAL-008', %s::date, 5000,
          'completed', %s::uuid, %s::uuid
        )
        ON CONFLICT (org_id, payment_reference) DO UPDATE SET status='completed', updated_at=NOW()
        """,
        (pay2, ORG_ID, COMPANY_ID, VENDOR_IDS["LOCAL"], (today - timedelta(days=5)).isoformat(), BANK_ID, ADMIN_USER_ID),
    )
    cur.execute(
        "SELECT id::text FROM erp.ap_payments WHERE org_id=%s::uuid AND payment_reference='PAY-LOCAL-008'",
        (ORG_ID,),
    )
    pay2 = (cur.fetchone() or [pay2])[0]
    cur.execute(
        """
        INSERT INTO erp.ap_payment_allocations (id, org_id, payment_id, invoice_id, amount)
        VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, 5000)
        ON CONFLICT (id) DO NOTHING
        """,
        (_uid("payalloc:local008"), ORG_ID, pay2, AP_INV["INV-008"]),
    )


def seed_ar(cur, today: date) -> None:
    _set_org(cur, ORG_ID)

    def insert_ar(
        number: str,
        cust: str,
        inv_date: date,
        due: date,
        sub: float,
        gst: float,
        status: str,
        paid: float = 0.0,
    ) -> str:
        iid = _uid(f"ar:{number}")
        total = sub + gst
        cur.execute(
            """
            INSERT INTO erp.ar_invoices (
              id, org_id, company_id, customer_id, invoice_number, invoice_date, due_date,
              subtotal, gst_amount, total_amount, paid_amount, status, created_by, issued_by, metadata
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date,
              %s, %s, %s, %s, %s, %s::uuid, %s::uuid, %s::jsonb
            )
            ON CONFLICT (org_id, customer_id, invoice_number) DO UPDATE SET
              status = EXCLUDED.status,
              paid_amount = EXCLUDED.paid_amount,
              updated_at = NOW()
            RETURNING id::text
            """,
            (
                iid,
                ORG_ID,
                COMPANY_ID,
                CUSTOMER_IDS[cust],
                number,
                inv_date.isoformat(),
                due.isoformat(),
                sub,
                gst,
                total,
                paid,
                status,
                ADMIN_USER_ID,
                ADMIN_USER_ID if status != "draft" else None,
                json.dumps({"seed": "demo_tenant"}),
            ),
        )
        row = cur.fetchone()
        real_id = row[0] if row else iid
        cur.execute(
            """
            INSERT INTO erp.ar_invoice_lines (
              id, org_id, invoice_id, line_type, account_id, description, amount, tax_code
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, 'revenue', %s::uuid, %s, %s, 'GST18'
            )
            ON CONFLICT (id) DO NOTHING
            """,
            (_uid(f"arline:{number}"), ORG_ID, real_id, ACCT["revenue"], number, sub),
        )
        return real_id

    ar1 = insert_ar("AR-001", "RELIANCE", today - timedelta(days=12), today + timedelta(days=18), 250000, 45000, "issued")
    ar2 = insert_ar("AR-002", "WIPRO", today - timedelta(days=50), today - timedelta(days=5), 175000, 31500, "overdue")
    ar3 = insert_ar("AR-003", "RETAIL1", today - timedelta(days=20), today - timedelta(days=10), 15000, 2700, "paid", 17700)
    ar4 = insert_ar("AR-004", "GOV1", today - timedelta(days=5), today + timedelta(days=55), 500000, 90000, "issued")
    ar5 = insert_ar("AR-005", "WIPRO", today - timedelta(days=2), today + timedelta(days=43), 90000, 16200, "partially_paid", 50000)

    # Receipts
    for rnum, cust, amount, inv_id, mode, status in [
        ("RCT-001", "RETAIL1", 17700, ar3, "upi", "completed"),
        ("RCT-002", "WIPRO", 50000, ar5, "bank_transfer", "completed"),
        ("RCT-003", "RELIANCE", 250000, ar1, "bank_transfer", "recorded"),
    ]:
        rid = _uid(f"rct:{rnum}")
        cur.execute(
            """
            INSERT INTO erp.customer_receipts (
              id, org_id, company_id, customer_id, receipt_number, receipt_date, amount,
              payment_mode, bank_account_id, status, created_by
            ) VALUES (
              %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s,
              %s, %s::uuid, %s, %s::uuid
            )
            ON CONFLICT (org_id, receipt_number) DO UPDATE SET
              status = EXCLUDED.status,
              amount = EXCLUDED.amount,
              updated_at = NOW()
            """,
            (
                rid,
                ORG_ID,
                COMPANY_ID,
                CUSTOMER_IDS[cust],
                rnum,
                (today - timedelta(days=4)).isoformat(),
                amount,
                mode,
                ACCT["bank"],
                status,
                ADMIN_USER_ID,
            ),
        )
        cur.execute(
            "SELECT id::text FROM erp.customer_receipts WHERE org_id=%s::uuid AND receipt_number=%s",
            (ORG_ID, rnum),
        )
        rid = (cur.fetchone() or [rid])[0]
        cur.execute(
            """
            INSERT INTO erp.customer_receipt_allocations (id, org_id, receipt_id, invoice_id, amount)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            (_uid(f"ralloc:{rnum}"), ORG_ID, rid, inv_id, amount if rnum != "RCT-003" else 100000),
        )

    for key, amt in [("RELIANCE", 295000), ("WIPRO", 206500 + 56200), ("GOV1", 590000), ("RETAIL1", 0)]:
        cur.execute(
            """
            INSERT INTO erp.customer_balances (id, org_id, customer_id, outstanding_amount, credit_used)
            VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)
            ON CONFLICT (org_id, customer_id) DO UPDATE SET
              outstanding_amount = EXCLUDED.outstanding_amount,
              last_updated = NOW()
            """,
            (_uid(f"cbal:{key}"), ORG_ID, CUSTOMER_IDS[key], amt, amt),
        )


def seed_journals_and_gst(cur, today: date, periods: dict[str, str]) -> None:
    _set_org(cur, ORG_ID)
    period_key = today.strftime("%Y-%m")
    _ = periods.get(period_key) or (next(iter(periods.values())) if periods else None)

    jid = _uid("jrnl:ap001")
    cur.execute(
        "SELECT id::text, journal_status FROM erp.journals WHERE org_id=%s::uuid AND journal_number='JV-AP-001'",
        (ORG_ID,),
    )
    existing = cur.fetchone()
    if existing and existing[1] == "posted":
        jid = existing[0]
    else:
        if existing:
            # Reset to draft so lines can be rewritten
            cur.execute(
                """
                UPDATE erp.journals SET journal_status='draft', updated_at=NOW()
                WHERE id=%s::uuid AND org_id=%s::uuid
                """,
                (existing[0], ORG_ID),
            )
            jid = existing[0]
            cur.execute(
                "DELETE FROM erp.journal_lines WHERE org_id=%s::uuid AND journal_id=%s::uuid",
                (ORG_ID, jid),
            )
        else:
            cur.execute(
                """
                INSERT INTO erp.journals (
                  id, org_id, company_id, journal_number, journal_type, journal_status, posting_date,
                  description, source_type, source_id, created_by
                ) VALUES (
                  %s::uuid, %s::uuid, %s::uuid, 'JV-AP-001', 'ap_invoice', 'draft', %s::date,
                  'Posting for AP INV-001 ACME', 'ap_invoice', %s::uuid, %s::uuid
                )
                """,
                (
                    jid,
                    ORG_ID,
                    COMPANY_ID,
                    (today - timedelta(days=25)).isoformat(),
                    AP_INV["INV-001"],
                    ADMIN_USER_ID,
                ),
            )
        lines = [
            (ACCT["expense_ops"], 100000, 0, "ACME expense"),
            (ACCT["gst_input"], 18000, 0, "GST input"),
            (ACCT["ap"], 0, 118000, "AP ACME"),
        ]
        for i, (acct, debit, credit, desc) in enumerate(lines, start=1):
            cur.execute(
                """
                INSERT INTO erp.journal_lines (
                  id, org_id, journal_id, account_id, line_description, debit_amount, credit_amount, company_id
                ) VALUES (
                  %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::uuid
                )
                ON CONFLICT (id) DO NOTHING
                """,
                (_uid(f"jl:ap001:{i}"), ORG_ID, jid, acct, desc, debit, credit, COMPANY_ID),
            )
        cur.execute(
            """
            UPDATE erp.journals
            SET journal_status='posted', posted_by=%s::uuid, posted_at=NOW(), updated_at=NOW()
            WHERE id=%s::uuid AND org_id=%s::uuid
            """,
            (ADMIN_USER_ID, jid, ORG_ID),
        )

    cur.execute(
        "UPDATE erp.ap_invoices SET journal_id=%s::uuid WHERE id=%s::uuid AND org_id=%s::uuid",
        (jid, AP_INV["INV-001"], ORG_ID),
    )

    # GST transactions for this month liability story
    if _table_exists(cur, "erp", "gst_transactions"):
        gst_rows = [
            ("ap_invoice", AP_INV["INV-001"], "input", 100000, 9000, 9000, 0, 18),
            ("ap_invoice", AP_INV["INV-003"], "input", 200000, 18000, 18000, 0, 18),
            ("ar_invoice", _uid("ar:AR-001"), "output", 250000, 22500, 22500, 0, 18),
            ("ar_invoice", _uid("ar:AR-004"), "output", 500000, 45000, 45000, 0, 18),
        ]
        for src_type, src_id, gst_type, taxable, cgst, sgst, igst, rate in gst_rows:
            cur.execute(
                """
                INSERT INTO erp.gst_transactions (
                  id, org_id, company_id, source_type, source_id, gst_type,
                  taxable_value, cgst_amount, sgst_amount, igst_amount, gst_rate,
                  invoice_date, place_of_supply, return_period
                ) VALUES (
                  %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid, %s,
                  %s, %s, %s, %s, %s, %s::date, '29', %s
                )
                ON CONFLICT (org_id, source_type, source_id, gst_type) DO UPDATE SET
                  taxable_value = EXCLUDED.taxable_value,
                  cgst_amount = EXCLUDED.cgst_amount,
                  sgst_amount = EXCLUDED.sgst_amount
                """,
                (
                    _uid(f"gstx:{src_type}:{gst_type}:{src_id[-6:]}"),
                    ORG_ID,
                    COMPANY_ID,
                    src_type,
                    src_id,
                    gst_type,
                    taxable,
                    cgst,
                    sgst,
                    igst,
                    rate,
                    today.isoformat(),
                    today.strftime("%Y-%m"),
                ),
            )

    if _table_exists(cur, "erp", "gst_returns"):
        # Avoid ON CONFLICT DO NOTHING without constraint — upsert by period
        cur.execute(
            """
            SELECT id::text FROM erp.gst_returns
            WHERE org_id=%s::uuid AND return_type='GSTR3B' AND return_period=%s
            """,
            (ORG_ID, today.strftime("%Y-%m")),
        )
        existing_ret = cur.fetchone()
        payload = json.dumps(
            {"output_liability": 135000, "itc": 54000, "net_payable": 81000, "seed": True}
        )
        if existing_ret:
            cur.execute(
                "UPDATE erp.gst_returns SET payload=%s::jsonb, status='draft' WHERE id=%s::uuid",
                (payload, existing_ret[0]),
            )
        else:
            cur.execute(
                """
                INSERT INTO erp.gst_returns (id, org_id, return_type, return_period, status, payload)
                VALUES (%s::uuid, %s::uuid, 'GSTR3B', %s, 'draft', %s::jsonb)
                """,
                (_uid(f"gstr:{today.strftime('%Y%m')}"), ORG_ID, today.strftime("%Y-%m"), payload),
            )


def seed_billing_and_analytics(cur) -> None:
    _set_org(cur, ORG_ID)
    if _table_exists(cur, "billing", "org_subscriptions"):
        cur.execute(
            """
            INSERT INTO billing.org_subscriptions (id, org_id, plan_key, status)
            VALUES (%s::uuid, %s::uuid, 'enterprise', 'active')
            ON CONFLICT (org_id) DO UPDATE SET plan_key='enterprise', status='active', updated_at=NOW()
            """,
            (str(uuid4()), ORG_ID),
        )
    if _table_exists(cur, "billing", "org_credit_wallets"):
        cur.execute(
            """
            INSERT INTO billing.org_credit_wallets (id, org_id, balance, included_monthly, purchased_balance)
            VALUES (%s::uuid, %s::uuid, 8000, 3000, 5000)
            ON CONFLICT (org_id) DO UPDATE SET
              balance = GREATEST(billing.org_credit_wallets.balance, EXCLUDED.balance),
              updated_at = NOW()
            """,
            (str(uuid4()), ORG_ID),
        )
    if _table_exists(cur, "finance_analytics", "kpi_snapshots"):
        today = date.today().isoformat()
        kpis = {
            "treasury.cash_runway_days": 52.0,
            "treasury.liquidity_coverage": 1.35,
            "finance.net_profit_margin": 14.2,
            "finance.gross_profit_margin": 34.0,
            "finance.ebitda_margin": 28.5,
            "collections.dso": 41.0,
            "vendor.dpo": 39.0,
            "compliance.filing_pct": 96.0,
            "close.efficiency_score": 88.0,
            "forecast.accuracy_avg": 12.5,
            "working_capital.net": 245000.0,
        }
        for code, val in kpis.items():
            cur.execute(
                """
                INSERT INTO finance_analytics.kpi_snapshots (org_id, kpi_code, kpi_value, snapshot_date)
                VALUES (%s::uuid, %s, %s, %s::date)
                ON CONFLICT (org_id, kpi_code, snapshot_date) DO UPDATE SET kpi_value = EXCLUDED.kpi_value
                """,
                (ORG_ID, code, val, today),
            )
    if _table_exists(cur, "finance_analytics", "executive_insights"):
        for iid, itype, title, desc, sev in [
            (
                _uid("insight:cash1"),
                "cash",
                "Cash runway healthy",
                "Demo tenant cash runway is above 45 days based on current burn.",
                "info",
            ),
            (
                _uid("insight:dso1"),
                "collections",
                "Watch DSO drift",
                "Collections DSO is elevated vs target; follow up on overdue AR.",
                "warning",
            ),
        ]:
            cur.execute(
                """
                INSERT INTO finance_analytics.executive_insights (
                  id, org_id, insight_type, title, description, severity, generated_at
                )
                VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                  title = EXCLUDED.title,
                  description = EXCLUDED.description,
                  severity = EXCLUDED.severity,
                  generated_at = NOW()
                """,
                (iid, ORG_ID, itype, title, desc, sev),
            )


def seed(dsn: str, password: str) -> dict:
    today = date.today()
    summary: dict = {"org_id": ORG_ID, "company_id": COMPANY_ID}

    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            seed_org_and_company(cur)
            seed_roles_and_users(cur, password)
            seed_coa(cur)
            periods = seed_fiscal(cur, today)
            seed_tax(cur)
            seed_parties(cur)
            seed_banking(cur, today)
            seed_procurement(cur, today)
            seed_ap(cur, today)
            seed_ar(cur, today)
            seed_journals_and_gst(cur, today, periods)
            seed_billing_and_analytics(cur)

            # Counts for report
            _set_org(cur, ORG_ID)
            for label, sql in [
                ("vendors", "SELECT count(*) FROM erp.vendors WHERE org_id=%s::uuid"),
                ("customers", "SELECT count(*) FROM erp.customers WHERE org_id=%s::uuid"),
                ("ap_invoices", "SELECT count(*) FROM erp.ap_invoices WHERE org_id=%s::uuid"),
                ("ar_invoices", "SELECT count(*) FROM erp.ar_invoices WHERE org_id=%s::uuid"),
                ("purchase_orders", "SELECT count(*) FROM erp.purchase_orders WHERE org_id=%s::uuid"),
                ("bank_txns", "SELECT count(*) FROM erp.bank_transactions WHERE org_id=%s::uuid"),
                ("coa_accounts", "SELECT count(*) FROM erp.chart_of_accounts WHERE org_id=%s::uuid"),
            ]:
                cur.execute(sql, (ORG_ID,))
                summary[label] = cur.fetchone()[0]

    summary["email"] = DEFAULT_EMAIL
    summary["password"] = password
    summary["ap_email"] = AP_EMAIL
    summary["ar_email"] = AR_EMAIL
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Flora Demo ERP tenant")
    parser.add_argument("--dsn", help="Postgres DSN (defaults to POSTGRES_DSN from .env)")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password for demo users")
    args = parser.parse_args()

    dsn = args.dsn or os.environ.get("POSTGRES_DSN") or _load_dsn_from_env()
    if not dsn:
        print("ERROR: No DSN. Pass --dsn or set POSTGRES_DSN in backend/apps/api/.env", file=sys.stderr)
        return 1

    result = seed(dsn, args.password)
    print("Flora Demo tenant seeded.\n")
    print(f"  Org:         {ORG_NAME}")
    print(f"  Org ID:      {result['org_id']}")
    print(f"  Company ID:  {result['company_id']}")
    print(f"  Admin:       {result['email']} / {result['password']}")
    print(f"  AP user:     {result['ap_email']} / {result['password']}")
    print(f"  AR user:     {result['ar_email']} / {result['password']}")
    print("\n  Counts:")
    for k in ("vendors", "customers", "ap_invoices", "ar_invoices", "purchase_orders", "bank_txns", "coa_accounts"):
        print(f"    {k}: {result.get(k)}")
    print("\n  Suggested AI prompts:")
    print('    - "Show my unpaid AP invoices"')
    print('    - "Which invoices are overdue?"')
    print('    - "Why hasn\'t INV-001 been paid?"')
    print('    - "Find duplicate invoices"')
    print('    - "Submit invoice INV-002"')
    print('    - "Reconcile this payment"')
    print('    - "Show me this month\'s GST liability"')
    print('    - "How many AP invoices this month?"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
