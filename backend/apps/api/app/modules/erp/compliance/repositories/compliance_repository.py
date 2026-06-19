from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


LEGACY_TYPE_MAP = {
    "GSTR-1": "GST_GSTR1",
    "GSTR-3B": "GST_GSTR3B",
    "TDS": "TDS_CHALLAN",
    "TAX_PAYMENT": "GST_PAYMENT",
    "ANNUAL_GST": "GST_GSTR3B",
    "AUDIT": "AUDIT_INTERNAL",
}


class ComplianceTypeRepository:
    def list_active(self) -> list[dict]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, compliance_code, compliance_name, regulator, frequency, metadata
                    FROM erp.compliance_types WHERE is_active = true ORDER BY compliance_code
                    """
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get_by_code(self, compliance_code: str) -> dict | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, compliance_code, compliance_name, regulator, frequency, metadata
                    FROM erp.compliance_types WHERE compliance_code = %s LIMIT 1
                    """,
                    (compliance_code,),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_id(self, type_id: str) -> dict | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, compliance_code, compliance_name, regulator, frequency, metadata
                    FROM erp.compliance_types WHERE id = %s::uuid LIMIT 1
                    """,
                    (type_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None


class ComplianceRuleRepository:
    def list(self, org_id: str, *, active_only: bool = True) -> list[dict]:
        where = ["r.org_id = %s::uuid"]
        params: list = [org_id]
        if active_only:
            where.append("r.is_active = true")
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT r.id::text, r.compliance_type_id::text, t.compliance_code, t.compliance_name,
                           r.due_day, r.month_offset, r.frequency, r.reminder_offsets_days, r.escalation_levels,
                           r.metadata, t.regulator
                    FROM erp.compliance_rules r
                    JOIN erp.compliance_types t ON t.id = r.compliance_type_id
                    WHERE {' AND '.join(where)}
                    ORDER BY t.compliance_code
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def upsert(self, org_id: str, *, compliance_type_id: str, **fields) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.compliance_rules (
                      id, org_id, compliance_type_id, due_day, month_offset, frequency,
                      reminder_offsets_days, escalation_levels, metadata
                    ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                    ON CONFLICT (org_id, compliance_type_id) DO UPDATE SET
                      due_day = EXCLUDED.due_day,
                      month_offset = EXCLUDED.month_offset,
                      frequency = EXCLUDED.frequency,
                      reminder_offsets_days = EXCLUDED.reminder_offsets_days,
                      escalation_levels = EXCLUDED.escalation_levels,
                      metadata = EXCLUDED.metadata,
                      is_active = true
                    RETURNING id::text, compliance_type_id::text, due_day, month_offset, frequency
                    """,
                    (
                        rid,
                        org_id,
                        compliance_type_id,
                        fields.get("due_day", 1),
                        fields.get("month_offset", 1),
                        fields.get("frequency", "monthly"),
                        Json(fields.get("reminder_offsets_days") or [30, 15, 7, 3, 1]),
                        Json(fields.get("escalation_levels") or ["assignee", "manager", "finance_head", "cfo"]),
                        Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def seed_defaults_for_org(self, org_id: str) -> int:
        defaults = [
            ("GST_GSTR1", 11, 1, "monthly"),
            ("GST_GSTR3B", 20, 1, "monthly"),
            ("GST_PAYMENT", 20, 1, "monthly"),
            ("TDS_CHALLAN", 7, 1, "monthly"),
            ("TDS_26Q", 31, 3, "quarterly"),
            ("AUDIT_INTERNAL", 30, 9, "annual"),
        ]
        count = 0
        type_repo = ComplianceTypeRepository()
        for code, due_day, month_offset, frequency in defaults:
            t = type_repo.get_by_code(code)
            if not t:
                continue
            self.upsert(org_id, compliance_type_id=t["id"], due_day=due_day, month_offset=month_offset, frequency=frequency)
            count += 1
        return count


class ComplianceObligationRepository:
    def create(self, org_id: str, **fields) -> dict:
        oid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.compliance_obligations (
                      id, org_id, compliance_type_id, title, due_date, return_period,
                      status, priority, assigned_to, metadata
                    ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s,%s,%s,%s::uuid,%s::jsonb)
                    ON CONFLICT (org_id, compliance_type_id, return_period) DO UPDATE SET
                      due_date = EXCLUDED.due_date,
                      title = EXCLUDED.title,
                      updated_at = NOW()
                    RETURNING id::text, title, due_date::text, return_period, status, priority
                    """,
                    (
                        oid,
                        org_id,
                        fields["compliance_type_id"],
                        fields["title"],
                        fields["due_date"],
                        fields.get("return_period"),
                        fields.get("status", "upcoming"),
                        fields.get("priority", "medium"),
                        fields.get("assigned_to"),
                        Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": oid})

    def get(self, org_id: str, obligation_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT o.id::text, o.title, o.due_date::text, o.return_period, o.status, o.priority,
                           o.assigned_to::text, o.completed_at::text, o.waived_at::text, o.waive_reason,
                           o.metadata, t.compliance_code, t.compliance_name, t.regulator
                    FROM erp.compliance_obligations o
                    JOIN erp.compliance_types t ON t.id = o.compliance_type_id
                    WHERE o.org_id = %s::uuid AND o.id = %s::uuid
                    """,
                    (org_id, obligation_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        status: str | None = None,
        priority: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        assigned_to: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        where = ["o.org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("o.status = %s")
            params.append(status)
        if priority:
            where.append("o.priority = %s")
            params.append(priority)
        if from_date:
            where.append("o.due_date >= %s::date")
            params.append(from_date)
        if to_date:
            where.append("o.due_date <= %s::date")
            params.append(to_date)
        if assigned_to:
            where.append("o.assigned_to = %s::uuid")
            params.append(assigned_to)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT o.id::text, o.compliance_type_id::text, o.title, o.due_date::text, o.return_period, o.status, o.priority,
                           o.assigned_to::text, t.compliance_code, t.compliance_name, t.regulator, o.metadata
                    FROM erp.compliance_obligations o
                    JOIN erp.compliance_types t ON t.id = o.compliance_type_id
                    WHERE {' AND '.join(where)}
                    ORDER BY o.due_date ASC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def update(self, org_id: str, obligation_id: str, **fields) -> dict:
        sets = ["updated_at = NOW()"]
        params: list = []
        for key in ("title", "due_date", "status", "priority", "assigned_to", "metadata"):
            if key in fields and fields[key] is not None:
                if key == "metadata":
                    sets.append("metadata = %s::jsonb")
                    params.append(Json(fields[key]))
                elif key == "assigned_to":
                    sets.append("assigned_to = %s::uuid")
                    params.append(fields[key])
                elif key == "due_date":
                    sets.append("due_date = %s::date")
                    params.append(fields[key])
                else:
                    sets.append(f"{key} = %s")
                    params.append(fields[key])
        params.extend([org_id, obligation_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.compliance_obligations SET {', '.join(sets)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, title, due_date::text, status, priority
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Obligation not found")
                return dict(row)

    def complete(self, org_id: str, obligation_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.compliance_obligations
                    SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid AND status NOT IN ('completed', 'waived')
                    RETURNING id::text, title, due_date::text, return_period, status,
                              compliance_type_id::text,
                              (SELECT compliance_code FROM erp.compliance_types t WHERE t.id = compliance_type_id) AS compliance_code
                    """,
                    (org_id, obligation_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Obligation not found or already closed")
                return dict(row)

    def complete_by_type_period(self, org_id: str, *, compliance_code: str, return_period: str | None) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if return_period:
                    cur.execute(
                        """
                        UPDATE erp.compliance_obligations o
                        SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                        FROM erp.compliance_types t
                        WHERE o.compliance_type_id = t.id AND o.org_id = %s::uuid
                          AND t.compliance_code = %s AND o.return_period = %s
                          AND o.status NOT IN ('completed', 'waived')
                        """,
                        (org_id, compliance_code, return_period),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE erp.compliance_obligations o
                        SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                        FROM erp.compliance_types t
                        WHERE o.compliance_type_id = t.id AND o.org_id = %s::uuid
                          AND t.compliance_code = %s
                          AND o.status NOT IN ('completed', 'waived')
                        """,
                        (org_id, compliance_code),
                    )
                return cur.rowcount

    def waive(self, org_id: str, obligation_id: str, *, reason: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.compliance_obligations
                    SET status = 'waived', waived_at = NOW(), waive_reason = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid AND status NOT IN ('completed', 'waived')
                    RETURNING id::text, title, status, waive_reason
                    """,
                    (reason, org_id, obligation_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Obligation not found or already closed")
                return dict(row)

    def refresh_all_statuses(self, org_id: str, *, status_updates: list[tuple[str, str]]) -> int:
        count = 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for oid, new_status in status_updates:
                    cur.execute(
                        """
                        UPDATE erp.compliance_obligations
                        SET status = %s, priority = CASE WHEN %s = 'overdue' THEN 'critical'
                            WHEN %s = 'due_soon' THEN 'high' ELSE priority END,
                            updated_at = NOW()
                        WHERE org_id = %s::uuid AND id = %s::uuid AND status NOT IN ('completed', 'waived')
                        """,
                        (new_status, new_status, new_status, org_id, oid),
                    )
                    count += cur.rowcount
        return count

    def count_overdue_critical(self, org_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM erp.compliance_obligations
                    WHERE org_id = %s::uuid AND status = 'overdue' AND priority IN ('critical', 'high')
                    """,
                    (org_id,),
                )
                return int((cur.fetchone() or {}).get("cnt") or 0)


class ComplianceReminderRepository:
    def create(self, org_id: str, *, obligation_id: str, reminder_date: str) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.compliance_reminders (id, org_id, obligation_id, reminder_date)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::date)
                    ON CONFLICT (org_id, obligation_id, reminder_date) DO NOTHING
                    RETURNING id::text, reminder_date::text
                    """,
                    (rid, org_id, obligation_id, reminder_date),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": rid, "reminder_date": reminder_date}

    def list_due_today(self, org_id: str, *, today: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.id::text, r.obligation_id::text, r.reminder_date::text,
                           o.title, o.due_date::text, t.compliance_code
                    FROM erp.compliance_reminders r
                    JOIN erp.compliance_obligations o ON o.id = r.obligation_id
                    JOIN erp.compliance_types t ON t.id = o.compliance_type_id
                    WHERE r.org_id = %s::uuid AND r.reminder_date = %s::date
                      AND r.notification_sent = false
                      AND o.status NOT IN ('completed', 'waived')
                    """,
                    (org_id, today),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def mark_sent(self, org_id: str, reminder_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.compliance_reminders SET notification_sent = true, sent_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, reminder_id),
                )


class ComplianceEscalationRepository:
    def create(self, org_id: str, *, obligation_id: str, level: int, role: str | None) -> dict:
        eid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.compliance_escalations (id, org_id, obligation_id, escalation_level, escalated_to_role)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s)
                    RETURNING id::text, escalation_level, escalated_to_role, escalated_at::text
                    """,
                    (eid, org_id, obligation_id, level, role),
                )
                return dict(cur.fetchone() or {"id": eid})

    def list_open(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.id::text, e.obligation_id::text, e.escalation_level, e.escalated_to_role,
                           e.escalated_at::text, o.title, o.due_date::text, t.compliance_code
                    FROM erp.compliance_escalations e
                    JOIN erp.compliance_obligations o ON o.id = e.obligation_id
                    JOIN erp.compliance_types t ON t.id = o.compliance_type_id
                    WHERE e.org_id = %s::uuid AND e.resolved = false
                    ORDER BY e.escalated_at DESC
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def max_level_for_obligation(self, org_id: str, obligation_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(MAX(escalation_level), 0) AS lvl
                    FROM erp.compliance_escalations
                    WHERE org_id = %s::uuid AND obligation_id = %s::uuid
                    """,
                    (org_id, obligation_id),
                )
                return int((cur.fetchone() or {}).get("lvl") or 0)


class CompliancePenaltyRepository:
    def upsert_estimate(self, org_id: str, *, obligation_id: str, penalty: float, interest: float) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.compliance_penalties (id, org_id, obligation_id, penalty_amount, interest_amount)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s)
                    ON CONFLICT DO NOTHING
                    RETURNING id::text, penalty_amount, interest_amount
                    """,
                    (pid, org_id, obligation_id, penalty, interest),
                )
                row = cur.fetchone()
                if row:
                    return dict(row)
                cur.execute(
                    """
                    SELECT id::text, penalty_amount, interest_amount FROM erp.compliance_penalties
                    WHERE org_id = %s::uuid AND obligation_id = %s::uuid ORDER BY calculated_at DESC LIMIT 1
                    """,
                    (org_id, obligation_id),
                )
                return dict(cur.fetchone() or {"id": pid, "penalty_amount": penalty, "interest_amount": interest})

    def total_exposure(self, org_id: str) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(p.penalty_amount + p.interest_amount), 0) AS total
                    FROM erp.compliance_penalties p
                    JOIN erp.compliance_obligations o ON o.id = p.obligation_id
                    WHERE p.org_id = %s::uuid AND o.status = 'overdue'
                    """,
                    (org_id,),
                )
                return float((cur.fetchone() or {}).get("total") or 0)

    def override(self, org_id: str, penalty_id: str, *, penalty_amount: float, interest_amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.compliance_penalties
                    SET penalty_amount = %s, interest_amount = %s, is_manual_override = true, calculated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, penalty_amount, interest_amount, is_manual_override
                    """,
                    (penalty_amount, interest_amount, org_id, penalty_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Penalty record not found")
                return dict(row)


compliance_type_repository = ComplianceTypeRepository()
compliance_rule_repository = ComplianceRuleRepository()
compliance_obligation_repository = ComplianceObligationRepository()
compliance_reminder_repository = ComplianceReminderRepository()
compliance_escalation_repository = ComplianceEscalationRepository()
compliance_penalty_repository = CompliancePenaltyRepository()
