from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org

DEFAULT_RULES = [
    ("amount_exact", "amount", 40.0),
    ("reference_match", "reference", 30.0),
    ("date_exact", "date", 20.0),
    ("narration_fuzzy", "narration", 10.0),
]


class RulesRepository:
    def list_active(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT rule_name, rule_type, weight, is_active
                    FROM erp.reconciliation_rules
                    WHERE org_id = %s::uuid AND is_active = true
                    """,
                    (org_id,),
                )
                rows = [dict(r) for r in (cur.fetchall() or [])]
        if rows:
            return rows
        return self.seed_defaults(org_id)

    def seed_defaults(self, org_id: str) -> list[dict]:
        seeded: list[dict] = []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for rule_name, rule_type, weight in DEFAULT_RULES:
                    rid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO erp.reconciliation_rules (id, org_id, rule_name, rule_type, weight, is_active)
                        VALUES (%s::uuid,%s::uuid,%s,%s,%s,true)
                        ON CONFLICT (org_id, rule_type) DO NOTHING
                        """,
                        (rid, org_id, rule_name, rule_type, weight),
                    )
                    seeded.append({"rule_name": rule_name, "rule_type": rule_type, "weight": weight, "is_active": True})
        return seeded


rules_repository = RulesRepository()
