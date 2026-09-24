"""Repository for platform.regulatory_* tables."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn
from app.services.schema_registry import table_ready


def _as_of(d: date | str | None) -> date:
    if d is None:
        return date.today()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def _effective_clause(alias: str = "t") -> str:
    return f"""
        {alias}.status = 'active'
        AND {alias}.effective_from <= %s
        AND ({alias}.effective_to IS NULL OR {alias}.effective_to >= %s)
    """


class RegulatoryRepository:
    def ready(self) -> bool:
        return table_ready("platform", "regulatory_param")

    def list_params(
        self,
        *,
        country_code: str = "IN",
        org_id: str | None = None,
        domain: str | None = None,
        include_global: bool = True,
    ) -> list[dict[str, Any]]:
        if not self.ready():
            return []
        clauses = ["country_code = %s"]
        params: list[Any] = [country_code]
        if org_id and include_global:
            clauses.append("(org_id IS NULL OR org_id = %s::uuid)")
            params.append(org_id)
        elif org_id:
            clauses.append("org_id = %s::uuid")
            params.append(org_id)
        else:
            clauses.append("org_id IS NULL")
        if domain:
            clauses.append("domain = %s")
            params.append(domain)
        sql = f"""
            SELECT id::text, country_code, domain, param_key, org_id::text,
                   value_numeric, value_text, value_json, unit, description,
                   effective_from::text, effective_to::text, status, updated_at
            FROM platform.regulatory_param
            WHERE {' AND '.join(clauses)}
            ORDER BY domain, param_key, effective_from DESC
        """
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def resolve_param_row(
        self,
        param_key: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        country_code: str = "IN",
    ) -> dict[str, Any] | None:
        if not self.ready():
            return None
        d = _as_of(as_of)
        # Prefer org override, then global
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                if org_id:
                    cur.execute(
                        f"""
                        SELECT id::text, param_key, value_numeric, value_text, value_json, unit, org_id::text
                        FROM platform.regulatory_param t
                        WHERE t.country_code = %s AND t.param_key = %s AND t.org_id = %s::uuid
                          AND {_effective_clause('t')}
                        ORDER BY t.effective_from DESC
                        LIMIT 1
                        """,
                        (country_code, param_key, org_id, d, d),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                cur.execute(
                    f"""
                    SELECT id::text, param_key, value_numeric, value_text, value_json, unit, org_id::text
                    FROM platform.regulatory_param t
                    WHERE t.country_code = %s AND t.param_key = %s AND t.org_id IS NULL
                      AND {_effective_clause('t')}
                    ORDER BY t.effective_from DESC
                    LIMIT 1
                    """,
                    (country_code, param_key, d, d),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_param(self, payload: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                pid = payload.get("id") or str(uuid4())
                cur.execute(
                    """
                    INSERT INTO platform.regulatory_param (
                        id, country_code, domain, param_key, org_id,
                        value_numeric, value_text, value_json, unit, description,
                        effective_from, effective_to, status, updated_by, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s::uuid, %s, %s, %s::jsonb, %s, %s,
                        %s::date, %s::date, %s, %s::uuid, NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        value_numeric = EXCLUDED.value_numeric,
                        value_text = EXCLUDED.value_text,
                        value_json = EXCLUDED.value_json,
                        unit = EXCLUDED.unit,
                        description = EXCLUDED.description,
                        effective_to = EXCLUDED.effective_to,
                        status = EXCLUDED.status,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = NOW()
                    RETURNING id::text, param_key, org_id::text, value_numeric, value_text, effective_from::text
                    """,
                    (
                        pid,
                        payload.get("country_code") or "IN",
                        payload.get("domain") or "general",
                        payload["param_key"],
                        payload.get("org_id"),
                        payload.get("value_numeric"),
                        payload.get("value_text"),
                        Json(payload.get("value_json") or {}),
                        payload.get("unit"),
                        payload.get("description"),
                        payload.get("effective_from") or date.today().isoformat(),
                        payload.get("effective_to"),
                        payload.get("status") or "active",
                        actor_id,
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def resolve_threshold(
        self,
        threshold_code: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        country_code: str = "IN",
    ) -> dict[str, Any] | None:
        if not table_ready("platform", "regulatory_threshold"):
            return None
        d = _as_of(as_of)
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                if org_id:
                    cur.execute(
                        f"""
                        SELECT id::text, threshold_code, amount, currency, org_id::text
                        FROM platform.regulatory_threshold t
                        WHERE t.country_code = %s AND t.threshold_code = %s AND t.org_id = %s::uuid
                          AND {_effective_clause('t')}
                        ORDER BY t.effective_from DESC LIMIT 1
                        """,
                        (country_code, threshold_code, org_id, d, d),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
                cur.execute(
                    f"""
                    SELECT id::text, threshold_code, amount, currency, org_id::text
                    FROM platform.regulatory_threshold t
                    WHERE t.country_code = %s AND t.threshold_code = %s AND t.org_id IS NULL
                      AND {_effective_clause('t')}
                    ORDER BY t.effective_from DESC LIMIT 1
                    """,
                    (country_code, threshold_code, d, d),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_thresholds(
        self, *, country_code: str = "IN", org_id: str | None = None
    ) -> list[dict[str, Any]]:
        if not table_ready("platform", "regulatory_threshold"):
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                if org_id:
                    cur.execute(
                        """
                        SELECT id::text, threshold_code, amount, currency, org_id::text,
                               description, effective_from::text, effective_to::text, status
                        FROM platform.regulatory_threshold
                        WHERE country_code = %s AND (org_id IS NULL OR org_id = %s::uuid)
                        ORDER BY threshold_code, effective_from DESC
                        """,
                        (country_code, org_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, threshold_code, amount, currency, org_id::text,
                               description, effective_from::text, effective_to::text, status
                        FROM platform.regulatory_threshold
                        WHERE country_code = %s AND org_id IS NULL
                        ORDER BY threshold_code, effective_from DESC
                        """,
                        (country_code,),
                    )
                return [dict(r) for r in cur.fetchall()]

    def upsert_threshold(self, payload: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                pid = payload.get("id") or str(uuid4())
                cur.execute(
                    """
                    INSERT INTO platform.regulatory_threshold (
                        id, country_code, threshold_code, org_id, amount, currency,
                        description, effective_from, effective_to, status, metadata, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s::uuid, %s, %s, %s, %s::date, %s::date, %s, %s::jsonb, NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        amount = EXCLUDED.amount,
                        description = EXCLUDED.description,
                        effective_to = EXCLUDED.effective_to,
                        status = EXCLUDED.status,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id::text, threshold_code, amount, org_id::text
                    """,
                    (
                        pid,
                        payload.get("country_code") or "IN",
                        payload["threshold_code"],
                        payload.get("org_id"),
                        payload["amount"],
                        payload.get("currency") or "INR",
                        payload.get("description"),
                        payload.get("effective_from") or date.today().isoformat(),
                        payload.get("effective_to"),
                        payload.get("status") or "active",
                        Json(payload.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def resolve_penalty(
        self,
        compliance_code: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        country_code: str = "IN",
    ) -> dict[str, Any] | None:
        if not table_ready("platform", "regulatory_penalty_formula"):
            return None
        d = _as_of(as_of)
        code = (compliance_code or "").upper()
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                for scope_org in ([org_id, None] if org_id else [None]):
                    if scope_org:
                        cur.execute(
                            f"""
                            SELECT * FROM (
                              SELECT id::text, formula_code, compliance_code_pattern,
                                     daily_fee, nil_daily_fee, fee_cap,
                                     interest_annual_pct, interest_monthly_pct,
                                     cap_by_turnover_json, metadata, org_id::text
                              FROM platform.regulatory_penalty_formula t
                              WHERE t.country_code = %s AND t.org_id = %s::uuid
                                AND {_effective_clause('t')}
                            ) x
                            ORDER BY CASE
                              WHEN compliance_code_pattern = %s THEN 0
                              WHEN %s LIKE REPLACE(REPLACE(compliance_code_pattern, '%%', ''), '*', '%%') THEN 1
                              WHEN %s LIKE RTRIM(compliance_code_pattern, '%%') || '%%' THEN 2
                              WHEN compliance_code_pattern = '*' THEN 9
                              ELSE 5
                            END
                            LIMIT 5
                            """,
                            (country_code, scope_org, d, d, code, code, code),
                        )
                    else:
                        cur.execute(
                            f"""
                            SELECT id::text, formula_code, compliance_code_pattern,
                                   daily_fee, nil_daily_fee, fee_cap,
                                   interest_annual_pct, interest_monthly_pct,
                                   cap_by_turnover_json, metadata, org_id::text
                            FROM platform.regulatory_penalty_formula t
                            WHERE t.country_code = %s AND t.org_id IS NULL
                              AND {_effective_clause('t')}
                            ORDER BY t.effective_from DESC
                            """,
                            (country_code, d, d),
                        )
                    rows = [dict(r) for r in cur.fetchall()]
                    match = self._match_penalty(rows, code)
                    if match:
                        return match
        return None

    def _match_penalty(self, rows: list[dict], code: str) -> dict[str, Any] | None:
        exact = [r for r in rows if str(r.get("compliance_code_pattern") or "").upper() == code]
        if exact:
            return exact[0]
        for r in rows:
            pat = str(r.get("compliance_code_pattern") or "")
            if pat.endswith("%") and code.startswith(pat[:-1].upper()):
                return r
            if pat == "*":
                continue
        wild = [r for r in rows if str(r.get("compliance_code_pattern") or "") == "*"]
        return wild[0] if wild else (rows[0] if rows else None)

    def list_penalties(self, *, country_code: str = "IN", org_id: str | None = None) -> list[dict[str, Any]]:
        if not table_ready("platform", "regulatory_penalty_formula"):
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                if org_id:
                    cur.execute(
                        """
                        SELECT id::text, formula_code, compliance_code_pattern, daily_fee, nil_daily_fee,
                               fee_cap, interest_annual_pct, interest_monthly_pct, cap_by_turnover_json,
                               org_id::text, effective_from::text, effective_to::text, status
                        FROM platform.regulatory_penalty_formula
                        WHERE country_code = %s AND (org_id IS NULL OR org_id = %s::uuid)
                        ORDER BY formula_code, effective_from DESC
                        """,
                        (country_code, org_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, formula_code, compliance_code_pattern, daily_fee, nil_daily_fee,
                               fee_cap, interest_annual_pct, interest_monthly_pct, cap_by_turnover_json,
                               org_id::text, effective_from::text, effective_to::text, status
                        FROM platform.regulatory_penalty_formula
                        WHERE country_code = %s AND org_id IS NULL
                        ORDER BY formula_code, effective_from DESC
                        """,
                        (country_code,),
                    )
                return [dict(r) for r in cur.fetchall()]

    def upsert_penalty(self, payload: dict[str, Any], *, actor_id: str | None = None) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                pid = payload.get("id") or str(uuid4())
                cur.execute(
                    """
                    INSERT INTO platform.regulatory_penalty_formula (
                        id, country_code, formula_code, compliance_code_pattern, org_id,
                        daily_fee, nil_daily_fee, fee_cap, interest_annual_pct, interest_monthly_pct,
                        cap_by_turnover_json, metadata, effective_from, effective_to, status, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s::uuid, %s, %s, %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::date, %s::date, %s, NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        daily_fee = EXCLUDED.daily_fee,
                        nil_daily_fee = EXCLUDED.nil_daily_fee,
                        fee_cap = EXCLUDED.fee_cap,
                        interest_annual_pct = EXCLUDED.interest_annual_pct,
                        interest_monthly_pct = EXCLUDED.interest_monthly_pct,
                        cap_by_turnover_json = EXCLUDED.cap_by_turnover_json,
                        status = EXCLUDED.status,
                        effective_to = EXCLUDED.effective_to,
                        updated_at = NOW()
                    RETURNING id::text, formula_code, daily_fee
                    """,
                    (
                        pid,
                        payload.get("country_code") or "IN",
                        payload["formula_code"],
                        payload.get("compliance_code_pattern") or "*",
                        payload.get("org_id"),
                        payload.get("daily_fee") or 0,
                        payload.get("nil_daily_fee"),
                        payload.get("fee_cap"),
                        payload.get("interest_annual_pct"),
                        payload.get("interest_monthly_pct"),
                        Json(payload.get("cap_by_turnover_json") or []),
                        Json(payload.get("metadata") or {}),
                        payload.get("effective_from") or date.today().isoformat(),
                        payload.get("effective_to"),
                        payload.get("status") or "active",
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def resolve_slab_set(
        self,
        set_code: str,
        *,
        org_id: str | None = None,
        as_of: date | str | None = None,
        country_code: str = "IN",
    ) -> dict[str, Any] | None:
        if not table_ready("platform", "regulatory_slab_set"):
            return None
        d = _as_of(as_of)
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                for scope_org in ([org_id, None] if org_id else [None]):
                    if scope_org:
                        cur.execute(
                            f"""
                            SELECT id::text, set_code, name, domain, org_id::text, effective_from::text
                            FROM platform.regulatory_slab_set t
                            WHERE t.country_code = %s AND t.set_code = %s AND t.org_id = %s::uuid
                              AND {_effective_clause('t')}
                            ORDER BY t.effective_from DESC LIMIT 1
                            """,
                            (country_code, set_code, scope_org, d, d),
                        )
                    else:
                        cur.execute(
                            f"""
                            SELECT id::text, set_code, name, domain, org_id::text, effective_from::text
                            FROM platform.regulatory_slab_set t
                            WHERE t.country_code = %s AND t.set_code = %s AND t.org_id IS NULL
                              AND {_effective_clause('t')}
                            ORDER BY t.effective_from DESC LIMIT 1
                            """,
                            (country_code, set_code, d, d),
                        )
                    row = cur.fetchone()
                    if not row:
                        continue
                    out = dict(row)
                    cur.execute(
                        """
                        SELECT sort_order, upper_limit, rate_pct
                        FROM platform.regulatory_slab_band
                        WHERE slab_set_id = %s::uuid
                        ORDER BY sort_order
                        """,
                        (out["id"],),
                    )
                    out["bands"] = [dict(r) for r in cur.fetchall()]
                    return out
        return None

    def list_slab_sets(self, *, country_code: str = "IN") -> list[dict[str, Any]]:
        if not table_ready("platform", "regulatory_slab_set"):
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, set_code, name, domain, org_id::text,
                           effective_from::text, effective_to::text, status
                    FROM platform.regulatory_slab_set
                    WHERE country_code = %s
                    ORDER BY set_code, effective_from DESC
                    """,
                    (country_code,),
                )
                return [dict(r) for r in cur.fetchall()]

    def replace_slab_bands(self, slab_set_id: str, bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM platform.regulatory_slab_band WHERE slab_set_id = %s::uuid", (slab_set_id,))
                out = []
                for i, b in enumerate(bands):
                    bid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO platform.regulatory_slab_band (id, slab_set_id, sort_order, upper_limit, rate_pct)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                        RETURNING id::text, sort_order, upper_limit, rate_pct
                        """,
                        (
                            bid,
                            slab_set_id,
                            int(b.get("sort_order", i + 1)),
                            b.get("upper_limit"),
                            b.get("rate_pct") or 0,
                        ),
                    )
                    out.append(dict(cur.fetchone() or {}))
                conn.commit()
                return out

    def upsert_slab_set(self, payload: dict[str, Any]) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                pid = payload.get("id") or str(uuid4())
                cur.execute(
                    """
                    INSERT INTO platform.regulatory_slab_set (
                        id, country_code, set_code, name, domain, org_id,
                        effective_from, effective_to, status, metadata, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s::uuid, %s::date, %s::date, %s, %s::jsonb, NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        status = EXCLUDED.status,
                        effective_to = EXCLUDED.effective_to,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id::text, set_code, name, org_id::text
                    """,
                    (
                        pid,
                        payload.get("country_code") or "IN",
                        payload["set_code"],
                        payload.get("name") or payload["set_code"],
                        payload.get("domain") or "income_tax",
                        payload.get("org_id"),
                        payload.get("effective_from") or date.today().isoformat(),
                        payload.get("effective_to"),
                        payload.get("status") or "active",
                        Json(payload.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def list_tds_templates(self, *, country_code: str = "IN") -> list[dict[str, Any]]:
        if not table_ready("platform", "regulatory_tds_section_template"):
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, section_code, section_name, description,
                           rate_pan, rate_no_pan, threshold_amount, payment_type,
                           effective_from::text, effective_to::text, status
                    FROM platform.regulatory_tds_section_template
                    WHERE country_code = %s AND status = 'active'
                    ORDER BY section_code
                    """,
                    (country_code,),
                )
                return [dict(r) for r in cur.fetchall()]

    def upsert_tds_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                pid = payload.get("id") or str(uuid4())
                cur.execute(
                    """
                    INSERT INTO platform.regulatory_tds_section_template (
                        id, country_code, section_code, section_name, description,
                        rate_pan, rate_no_pan, threshold_amount, payment_type,
                        effective_from, effective_to, status, metadata, updated_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s::date, %s::date, %s, %s::jsonb, NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        section_name = EXCLUDED.section_name,
                        rate_pan = EXCLUDED.rate_pan,
                        rate_no_pan = EXCLUDED.rate_no_pan,
                        threshold_amount = EXCLUDED.threshold_amount,
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    RETURNING id::text, section_code, rate_pan, rate_no_pan
                    """,
                    (
                        pid,
                        payload.get("country_code") or "IN",
                        payload["section_code"],
                        payload.get("section_name") or payload["section_code"],
                        payload.get("description"),
                        payload.get("rate_pan") or 0,
                        payload.get("rate_no_pan") or 20,
                        payload.get("threshold_amount") or 0,
                        payload.get("payment_type"),
                        payload.get("effective_from") or date.today().isoformat(),
                        payload.get("effective_to"),
                        payload.get("status") or "active",
                        Json(payload.get("metadata") or {}),
                    ),
                )
                row = dict(cur.fetchone() or {})
                conn.commit()
                return row

    def apply_tds_templates_to_org(self, org_id: str) -> int:
        templates = self.list_tds_templates()
        if not templates or not table_ready("erp", "tds_sections"):
            return 0
        count = 0
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                for t in templates:
                    cur.execute(
                        """
                        INSERT INTO erp.tds_sections (
                            id, org_id, section_code, section_name, description,
                            rate, rate_pan, rate_no_pan, threshold_amount
                        ) VALUES (
                            %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            str(uuid4()),
                            org_id,
                            t["section_code"],
                            t.get("section_name") or t["section_code"],
                            t.get("description"),
                            t.get("rate_pan") or 0,
                            t.get("rate_pan") or 0,
                            t.get("rate_no_pan") or 20,
                            t.get("threshold_amount") or 0,
                        ),
                    )
                    count += cur.rowcount
                conn.commit()
        return count

    def list_compliance_templates(self, *, country_code: str = "IN") -> list[dict[str, Any]]:
        if not table_ready("platform", "regulatory_compliance_template"):
            return []
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, compliance_code, due_day, month_offset, frequency,
                           reminder_offsets, escalation_levels, effective_from::text, status
                    FROM platform.regulatory_compliance_template
                    WHERE country_code = %s AND status = 'active'
                    ORDER BY compliance_code
                    """,
                    (country_code,),
                )
                return [dict(r) for r in cur.fetchall()]

    def write_audit(
        self,
        *,
        actor_user_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        org_id: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
    ) -> None:
        if not table_ready("platform", "regulatory_audit_log"):
            return
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO platform.regulatory_audit_log (
                        id, actor_user_id, entity_type, entity_id, action, org_id, before_json, after_json
                    ) VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s::jsonb, %s::jsonb)
                    """,
                    (
                        str(uuid4()),
                        actor_user_id,
                        entity_type,
                        entity_id,
                        action,
                        org_id,
                        Json(before or {}),
                        Json(after or {}),
                    ),
                )
                conn.commit()


regulatory_repository = RegulatoryRepository()
