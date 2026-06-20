from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


def _jsonb(value: dict | list | None):
    if value is None:
        return None
    return Json(value)


def _new_id() -> str:
    return str(uuid4())


def _uuid_or_none(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None


class SourcesRepository:
    def create_source(self, org_id: str, source_type: str, config_ref: str) -> dict:
        source_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO data_sources (id, org_id, type, status, config_ref, last_sync_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, NULL)
                    RETURNING id::text, type AS source_type, status, last_sync_at
                    """,
                    (source_id, org_id, source_type, "connected", config_ref),
                )
                row = cur.fetchone()
        return dict(row or {})

    def list_sources(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, type AS source_type, status, last_sync_at
                    FROM data_sources
                    WHERE org_id = %s::uuid
                    ORDER BY id DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def get_source(self, org_id: str, source_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, type AS source_type, status, last_sync_at
                    FROM data_sources
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (org_id, source_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_source_ref(self, org_id: str, source_id: str) -> str | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT config_ref
                    FROM data_sources
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (org_id, source_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return str(row.get("config_ref") or "")


class IngestionRepository:
    def create_run(self, org_id: str, source_id: str, status: str = "started") -> dict:
        run_id = _new_id()
        started_at = datetime.now(timezone.utc)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ingestion_runs (id, org_id, source_id, started_at, completed_at, status, error_summary)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, NULL, %s, NULL)
                    RETURNING id::text, source_id::text, status, started_at, completed_at, error_summary
                    """,
                    (run_id, org_id, source_id, started_at, status),
                )
                row = cur.fetchone()
        return dict(row or {})

    def complete_run(self, org_id: str, run_id: str, success: bool, error_summary: str | None) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingestion_runs
                    SET status = %s, completed_at = NOW(), error_summary = %s
                    WHERE org_id = %s::uuid AND id::text = %s
                    RETURNING id::text, source_id::text, status, started_at, completed_at, error_summary
                    """,
                    ("completed" if success else "failed", error_summary, org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_runs(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_id::text, status, started_at, completed_at, error_summary
                    FROM ingestion_runs
                    WHERE org_id = %s::uuid
                    ORDER BY started_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def reliability_counts(self, org_id: str) -> tuple[int, int]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)::int AS success_count,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END)::int AS failure_count
                    FROM ingestion_runs
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                row = cur.fetchone() or {"success_count": 0, "failure_count": 0}
                return int(row.get("success_count") or 0), int(row.get("failure_count") or 0)

    def upsert_identity_profile(self, org_id: str, canonical_type: str, canonical_key: str, confidence: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text
                    FROM identity_profiles
                    WHERE org_id = %s::uuid AND canonical_type = %s AND canonical_key = %s
                    LIMIT 1
                    """,
                    (org_id, canonical_type, canonical_key),
                )
                existing = cur.fetchone()
                if existing:
                    profile_id = str(existing["id"])
                    cur.execute(
                        """
                        UPDATE identity_profiles
                        SET confidence = GREATEST(confidence, %s)
                        WHERE org_id = %s::uuid AND id::text = %s
                        RETURNING id::text, canonical_type, canonical_key, confidence
                        """,
                        (confidence, org_id, profile_id),
                    )
                    return dict(cur.fetchone() or {})
                profile_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO identity_profiles (id, org_id, canonical_type, canonical_key, confidence)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    RETURNING id::text, canonical_type, canonical_key, confidence
                    """,
                    (profile_id, org_id, canonical_type, canonical_key, confidence),
                )
                return dict(cur.fetchone() or {})

    def upsert_identity_alias(self, org_id: str, profile_id: str, source: str, source_key: str, raw_value: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text
                    FROM identity_aliases
                    WHERE org_id = %s::uuid AND identity_profile_id::text = %s AND source = %s AND source_key = %s
                    LIMIT 1
                    """,
                    (org_id, profile_id, source, source_key),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        """
                        UPDATE identity_aliases
                        SET raw_value = %s
                        WHERE org_id = %s::uuid AND id::text = %s
                        """,
                        (raw_value, org_id, str(existing["id"])),
                    )
                    return
                alias_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO identity_aliases (id, org_id, identity_profile_id, source, source_key, raw_value)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s)
                    """,
                    (alias_id, org_id, profile_id, source, source_key, raw_value),
                )

    def get_connector_sync_state(self, org_id: str, connector: str, source_id: str | None, mode: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id::text,
                        connector,
                        mode,
                        source_id::text AS source_id,
                        cursor_ref,
                        metadata_jsonb,
                        updated_at
                    FROM connector_sync_states
                    WHERE org_id = %s::uuid
                      AND connector = %s
                      AND mode = %s
                      AND ((source_id IS NULL AND %s::uuid IS NULL) OR source_id = %s::uuid)
                    LIMIT 1
                    """,
                    (org_id, connector, mode, _uuid_or_none(source_id), _uuid_or_none(source_id)),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert_connector_sync_state(
        self,
        org_id: str,
        connector: str,
        source_id: str | None,
        mode: str,
        cursor_ref: str | None,
        metadata_jsonb: dict,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                resolved_source = _uuid_or_none(source_id)
                cur.execute(
                    """
                    INSERT INTO connector_sync_states (id, org_id, source_id, connector, mode, cursor_ref, metadata_jsonb, updated_at)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (org_id, connector, source_id, mode)
                    DO UPDATE SET
                        cursor_ref = EXCLUDED.cursor_ref,
                        metadata_jsonb = COALESCE(connector_sync_states.metadata_jsonb, '{}'::jsonb) || COALESCE(EXCLUDED.metadata_jsonb, '{}'::jsonb),
                        updated_at = NOW()
                    RETURNING id::text, connector, mode, source_id::text AS source_id, cursor_ref, metadata_jsonb, updated_at
                    """,
                    (_new_id(), org_id, resolved_source, connector, mode, cursor_ref, _jsonb(metadata_jsonb)),
                )
                return dict(cur.fetchone() or {})

    def has_processed_connector_record(self, org_id: str, connector: str, source_id: str | None, external_record_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM connector_processed_records
                    WHERE org_id = %s::uuid
                      AND connector = %s
                      AND external_record_id = %s
                      AND ((source_id IS NULL AND %s::uuid IS NULL) OR source_id = %s::uuid)
                    LIMIT 1
                    """,
                    (org_id, connector, external_record_id, _uuid_or_none(source_id), _uuid_or_none(source_id)),
                )
                return cur.fetchone() is not None

    def mark_connector_record_processed(
        self,
        org_id: str,
        connector: str,
        source_id: str | None,
        external_record_id: str,
        payload_hash: str,
        normalized_ref: str | None,
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO connector_processed_records (
                        id, org_id, source_id, connector, external_record_id, payload_hash, normalized_ref, processed_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, NOW())
                    ON CONFLICT (org_id, connector, source_id, external_record_id)
                    DO NOTHING
                    """,
                    (
                        _new_id(),
                        org_id,
                        _uuid_or_none(source_id),
                        connector,
                        external_record_id,
                        payload_hash,
                        normalized_ref,
                    ),
                )


class WorkflowsRepository:
    def list_workflows(
        self,
        org_id: str,
        workflow_type: str | None = None,
        status: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list[object] = [org_id]
        if workflow_type:
            clauses.append("workflow_type = %s")
            params.append(workflow_type)
        if status:
            normalized = status.strip().lower()
            if normalized == "pending":
                clauses.append("state IN ('pending', 'pending_approval')")
            else:
                clauses.append("state = %s")
                params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, workflow_type, state, owner_user_id::text, started_at, closed_at
                    FROM workflows
                    WHERE {' AND '.join(clauses)}
                    ORDER BY started_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]

    def get_workflow(self, org_id: str, workflow_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, workflow_type, state, owner_user_id::text, started_at, closed_at
                    FROM workflows
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (org_id, workflow_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def add_timeline_step(self, org_id: str, workflow_id: str, step_type: str, state: str) -> None:
        step_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_steps (id, org_id, workflow_id, step_type, state, started_at, ended_at)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, NOW(), NOW())
                    """,
                    (step_id, org_id, workflow_id, step_type, state),
                )

    def list_timeline(self, org_id: str, workflow_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        step_type AS event_type,
                        started_at AS occurred_at,
                        CONCAT('state=', state) AS detail
                    FROM workflow_steps
                    WHERE org_id = %s::uuid AND workflow_id::text = %s
                    ORDER BY started_at ASC
                    """,
                    (org_id, workflow_id),
                )
                return [dict(row) for row in cur.fetchall()]

    def workflow_state_counts(self, org_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*)::int AS total,
                        SUM(CASE WHEN state = 'blocked' THEN 1 ELSE 0 END)::int AS blocked_count,
                        SUM(CASE WHEN state = 'pending_approval' THEN 1 ELSE 0 END)::int AS pending_approval_count
                    FROM workflows
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return dict(cur.fetchone() or {"total": 0, "blocked_count": 0, "pending_approval_count": 0})


class InvoicesRepository:
    def get_invoice(self, org_id: str, invoice_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        i.id::text AS invoice_id,
                        i.amount::float8 AS amount,
                        i.status,
                        COALESCE(v.id::text, i.vendor_id::text, '') AS vendor
                    FROM invoices i
                    LEFT JOIN vendors v ON v.id = i.vendor_id
                    WHERE i.org_id = %s::uuid AND i.id::text = %s
                    """,
                    (org_id, invoice_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_invoice_policy_context(self, org_id: str, invoice_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        i.id::text AS invoice_id,
                        i.amount::float8 AS amount,
                        i.status,
                        i.invoice_type,
                        COALESCE(v.risk_tier, 'medium') AS vendor_risk
                    FROM invoices i
                    LEFT JOIN vendors v ON v.id = i.vendor_id AND v.org_id = i.org_id
                    WHERE i.org_id = %s::uuid AND i.id::text = %s
                    """,
                    (org_id, invoice_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def create_invoice(
        self,
        org_id: str,
        vendor_id: str | None,
        amount: float,
        due_date: str | None,
        invoice_type: str = "ap",
        customer_id: str | None = None,
        purchase_order_id: str | None = None,
    ) -> dict:
        invoice_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                vendor_uuid = _uuid_or_none(vendor_id)
                customer_uuid = _uuid_or_none(customer_id)
                po_uuid = _uuid_or_none(purchase_order_id)
                cur.execute(
                    """
                    INSERT INTO invoices (
                        id, org_id, invoice_type, vendor_id, customer_id, purchase_order_id,
                        amount, currency, due_date, status
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s::uuid, %s::uuid, %s, 'USD', %s::date, 'Pending')
                    RETURNING id::text AS invoice_id, status
                    """,
                    (invoice_id, org_id, invoice_type, vendor_uuid, customer_uuid, po_uuid, amount, due_date),
                )
                row = cur.fetchone()
                return dict(row or {"invoice_id": invoice_id, "status": "Pending"})


class CanonicalRepository:
    def upsert_finance_entity(self, org_id: str, entity_type: str, name: str, external_ref: str | None = None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if external_ref:
                    cur.execute(
                        """
                        SELECT id::text, entity_type, name, COALESCE(external_ref, '') AS external_ref
                        FROM finance_entities
                        WHERE org_id = %s::uuid AND entity_type = %s AND external_ref = %s
                        LIMIT 1
                        """,
                        (org_id, entity_type, external_ref),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, entity_type, name, COALESCE(external_ref, '') AS external_ref
                        FROM finance_entities
                        WHERE org_id = %s::uuid AND entity_type = %s AND name = %s
                        LIMIT 1
                        """,
                        (org_id, entity_type, name),
                    )
                existing = cur.fetchone()
                if existing:
                    return dict(existing)
                entity_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO finance_entities (id, org_id, entity_type, name, external_ref)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    RETURNING id::text, entity_type, name, COALESCE(external_ref, '') AS external_ref
                    """,
                    (entity_id, org_id, entity_type, name, external_ref),
                )
                return dict(cur.fetchone() or {})

    def upsert_vendor(self, org_id: str, finance_entity_id: str, payment_terms: str | None, risk_tier: str | None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, finance_entity_id::text, payment_terms, risk_tier
                    FROM vendors
                    WHERE org_id = %s::uuid AND finance_entity_id::text = %s
                    LIMIT 1
                    """,
                    (org_id, finance_entity_id),
                )
                existing = cur.fetchone()
                if existing:
                    vendor_id = str(existing["id"])
                    cur.execute(
                        """
                        UPDATE vendors
                        SET payment_terms = COALESCE(%s, payment_terms), risk_tier = COALESCE(%s, risk_tier)
                        WHERE org_id = %s::uuid AND id::text = %s
                        RETURNING id::text, finance_entity_id::text, payment_terms, risk_tier
                        """,
                        (payment_terms, risk_tier, org_id, vendor_id),
                    )
                    return dict(cur.fetchone() or {})
                vendor_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO vendors (id, org_id, finance_entity_id, payment_terms, risk_tier)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, finance_entity_id::text, payment_terms, risk_tier
                    """,
                    (vendor_id, org_id, finance_entity_id, payment_terms, risk_tier),
                )
                return dict(cur.fetchone() or {})


    def upsert_customer(self, org_id: str, finance_entity_id: str, segment: str | None, risk_tier: str | None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, finance_entity_id::text, segment, risk_tier
                    FROM customers
                    WHERE org_id = %s::uuid AND finance_entity_id::text = %s
                    LIMIT 1
                    """,
                    (org_id, finance_entity_id),
                )
                existing = cur.fetchone()
                if existing:
                    customer_id = str(existing["id"])
                    cur.execute(
                        """
                        UPDATE customers
                        SET segment = COALESCE(%s, segment), risk_tier = COALESCE(%s, risk_tier)
                        WHERE org_id = %s::uuid AND id::text = %s
                        RETURNING id::text, finance_entity_id::text, segment, risk_tier
                        """,
                        (segment, risk_tier, org_id, customer_id),
                    )
                    return dict(cur.fetchone() or {})
                customer_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO customers (id, org_id, finance_entity_id, segment, risk_tier)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, finance_entity_id::text, segment, risk_tier
                    """,
                    (customer_id, org_id, finance_entity_id, segment, risk_tier),
                )
                return dict(cur.fetchone() or {})

    def upsert_contract(
        self,
        org_id: str,
        contract_number: str,
        vendor_id: str | None,
        start_date: str | None,
        end_date: str | None,
        status: str = "active",
        risk_tier: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, contract_number, vendor_id::text AS vendor_id, status, risk_tier
                    FROM contracts
                    WHERE org_id = %s::uuid AND contract_number = %s
                    LIMIT 1
                    """,
                    (org_id, contract_number),
                )
                existing = cur.fetchone()
                vendor_uuid = _uuid_or_none(vendor_id)
                if existing:
                    contract_id = str(existing["id"])
                    cur.execute(
                        """
                        UPDATE contracts
                        SET vendor_id = COALESCE(%s::uuid, vendor_id),
                            start_date = COALESCE(%s::date, start_date),
                            end_date = COALESCE(%s::date, end_date),
                            status = COALESCE(%s, status),
                            risk_tier = COALESCE(%s, risk_tier)
                        WHERE org_id = %s::uuid AND id::text = %s
                        RETURNING id::text, contract_number, vendor_id::text AS vendor_id, status, risk_tier
                        """,
                        (vendor_uuid, start_date, end_date, status, risk_tier, org_id, contract_id),
                    )
                    return dict(cur.fetchone() or {})
                contract_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO contracts (id, org_id, vendor_id, contract_number, start_date, end_date, status, risk_tier)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date, %s, %s)
                    RETURNING id::text, contract_number, vendor_id::text AS vendor_id, status, risk_tier
                    """,
                    (contract_id, org_id, vendor_uuid, contract_number, start_date, end_date, status, risk_tier),
                )
                return dict(cur.fetchone() or {})

    def upsert_purchase_order(
        self,
        org_id: str,
        po_number: str,
        vendor_id: str | None,
        amount: float,
        purchase_date: str | None,
        contract_id: str | None = None,
        status: str = "open",
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, po_number, vendor_id::text AS vendor_id, contract_id::text AS contract_id, status
                    FROM purchase_orders
                    WHERE org_id = %s::uuid AND po_number = %s
                    LIMIT 1
                    """,
                    (org_id, po_number),
                )
                existing = cur.fetchone()
                vendor_uuid = _uuid_or_none(vendor_id)
                contract_uuid = _uuid_or_none(contract_id)
                if existing:
                    po_id = str(existing["id"])
                    cur.execute(
                        """
                        UPDATE purchase_orders
                        SET vendor_id = COALESCE(%s::uuid, vendor_id),
                            contract_id = COALESCE(%s::uuid, contract_id),
                            amount = %s,
                            purchase_date = COALESCE(%s::date, purchase_date),
                            status = COALESCE(%s, status)
                        WHERE org_id = %s::uuid AND id::text = %s
                        RETURNING id::text, po_number, vendor_id::text AS vendor_id, contract_id::text AS contract_id, status
                        """,
                        (vendor_uuid, contract_uuid, amount, purchase_date, status, org_id, po_id),
                    )
                    return dict(cur.fetchone() or {})
                po_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO purchase_orders (id, org_id, po_number, vendor_id, contract_id, purchase_date, amount, status)
                    VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s::uuid, %s::date, %s, %s)
                    RETURNING id::text, po_number, vendor_id::text AS vendor_id, contract_id::text AS contract_id, status
                    """,
                    (po_id, org_id, po_number, vendor_uuid, contract_uuid, purchase_date, amount, status),
                )
                return dict(cur.fetchone() or {})

    def upsert_payment(
        self,
        org_id: str,
        invoice_id: str | None,
        amount: float,
        payment_date: str | None,
        payment_method: str | None = None,
        status: str = "pending",
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                invoice_uuid = _uuid_or_none(invoice_id)
                payment_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO payments (id, org_id, invoice_id, amount, payment_date, payment_method, status)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s, %s)
                    RETURNING id::text, invoice_id::text AS invoice_id, amount::float8 AS amount, status
                    """,
                    (payment_id, org_id, invoice_uuid, amount, payment_date, payment_method, status),
                )
                return dict(cur.fetchone() or {})

    def upsert_journal_entry(
        self,
        org_id: str,
        period: str,
        entry_date: str,
        account_code: str,
        debit: float,
        credit: float,
        status: str = "posted",
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                entry_id = _new_id()
                cur.execute(
                    """
                    INSERT INTO journal_entries (id, org_id, period, entry_date, account_code, debit, credit, status)
                    VALUES (%s::uuid, %s::uuid, %s, %s::date, %s, %s, %s, %s)
                    RETURNING id::text, period, account_code, debit::float8 AS debit, credit::float8 AS credit, status
                    """,
                    (entry_id, org_id, period, entry_date, account_code, debit, credit, status),
                )
                return dict(cur.fetchone() or {})


class DecisionsRepository:
    def create_decision(self, org_id: str, decision_type: str, title: str, rationale: str, made_by: str) -> dict:
        decision_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO decisions (id, org_id, decision_type, title, rationale, made_by, decided_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, NULL, NOW())
                    RETURNING id::text, decision_type, title, rationale, %s::text AS made_by, decided_at
                    """,
                    (decision_id, org_id, decision_type, title, rationale, made_by),
                )
                row = cur.fetchone()
                return dict(row or {})

    def list_decisions(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, decision_type, title, rationale, ''::text AS made_by, decided_at
                    FROM decisions
                    WHERE org_id = %s::uuid
                    ORDER BY decided_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]


class MemoryRepository:
    def create_memory(self, org_id: str, memory_type: str, subject_ref: str, payload_jsonb: dict, relevance_score: float) -> dict:
        memory_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_records (id, org_id, memory_type, subject_ref, payload_jsonb, relevance_score, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, NOW())
                    RETURNING id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
                    """,
                    (memory_id, org_id, memory_type, subject_ref, _jsonb(payload_jsonb), relevance_score),
                )
                row = cur.fetchone()
                return dict(row or {})

    def list_memory(self, org_id: str, subject_ref: str | None = None, memory_type: str | None = None) -> list[dict]:
        query = """
            SELECT id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
            FROM memory_records
            WHERE org_id = %s::uuid
        """
        params: list = [org_id]
        if subject_ref:
            query += " AND subject_ref = %s"
            params.append(subject_ref)
        if memory_type:
            query += " AND memory_type = %s"
            params.append(memory_type)
        query += " ORDER BY created_at DESC"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                return [dict(row) for row in cur.fetchall()]

    def list_all_for_decay(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
                    FROM memory_records
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def update_memory_status(self, org_id: str, memory_id: str, status: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE memory_records
                    SET payload_jsonb = COALESCE(payload_jsonb, '{}'::jsonb) || jsonb_build_object('status', %s)
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (status, org_id, memory_id),
                )

    def list_high_relevance(self, org_id: str, min_relevance: float = 0.7) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, memory_type, subject_ref, payload_jsonb, relevance_score, created_at
                    FROM memory_records
                    WHERE org_id = %s::uuid AND relevance_score >= %s
                    ORDER BY relevance_score DESC, created_at DESC
                    """,
                    (org_id, min_relevance),
                )
                return [dict(row) for row in cur.fetchall()]


class AuditRepository:
    def create_log(self, org_id: str, actor_type: str, actor_id: str, event_type: str, object_ref: str, payload_jsonb: dict) -> dict:
        try:
            from app.core.request_context import get_request_context

            ctx = get_request_context()
            from app.modules.platform.governance.services.audit_service import audit_service

            return audit_service.record_legacy(
                org_id,
                actor_type,
                actor_id,
                event_type,
                object_ref,
                payload_jsonb,
                request_id=ctx.request_id,
                trace_id=ctx.trace_id,
                ip_address=ctx.ip_address,
                user_agent=ctx.user_agent,
            )
        except Exception:
            pass
        audit_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (id, org_id, actor_type, actor_id, event_type, object_ref, payload_jsonb, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s::jsonb, NOW())
                    RETURNING id::text, actor_type, actor_id, event_type, object_ref, payload_jsonb, created_at
                    """,
                    (audit_id, org_id, actor_type, actor_id, event_type, object_ref, _jsonb(payload_jsonb)),
                )
                row = cur.fetchone()
                return dict(row or {})

    def list_logs(self, org_id: str) -> list[dict]:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            return audit_service.list_logs(org_id, limit=500)
        except Exception:
            pass
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, actor_type, actor_id, event_type, object_ref, payload_jsonb, created_at
                    FROM audit_logs
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]


class AgentsRepository:
    def create_run(self, org_id: str, agent_type: str, trigger_type: str, status: str, outputs: dict) -> dict:
        run_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO agent_runs (id, org_id, agent_type, trigger_type, status, started_at, ended_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, NOW(), %s)
                    RETURNING id::text AS run_id, agent_type, trigger_type, status, started_at, ended_at
                    """,
                    (run_id, org_id, agent_type, trigger_type, status, datetime.now(timezone.utc) if status == "completed" else None),
                )
                row = dict(cur.fetchone() or {})
                row["outputs"] = outputs
                for action in outputs.get("flow_result", {}).get("proposed_actions", []):
                    action_id = _new_id()
                    cur.execute(
                        """
                        INSERT INTO agent_actions (id, org_id, agent_run_id, action_type, target_system, payload_jsonb, outcome, idempotency_key)
                        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s)
                        """,
                        (
                            action_id,
                            org_id,
                            run_id,
                            str(action.get("method", "unknown")),
                            str(action.get("tool", "unknown")),
                            _jsonb(action),
                            "pending" if status == "pending_human_approval" else "planned",
                            f"{run_id}:{str(action.get('tool', 'unknown'))}:{str(action.get('method', 'unknown'))}:{action_id}",
                        ),
                    )
                return row

    def get_run(self, org_id: str, run_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS run_id, agent_type, trigger_type, status, started_at, ended_at
                    FROM agent_runs
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (org_id, run_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                record = dict(row)
                cur.execute(
                    """
                    SELECT payload_jsonb, outcome, target_system, action_type
                    FROM agent_actions
                    WHERE org_id = %s::uuid AND agent_run_id::text = %s
                    ORDER BY id ASC
                    """,
                    (org_id, run_id),
                )
                action_rows = [dict(item) for item in cur.fetchall()]
                record["outputs"] = {"actions": action_rows}
                return record

    def approve_run(self, org_id: str, run_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_runs
                    SET status = 'approved', ended_at = NOW()
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (org_id, run_id),
                )
                return cur.rowcount > 0

    def list_pending_actions(self, org_id: str, run_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS action_id, payload_jsonb, target_system, action_type, outcome
                    FROM agent_actions
                    WHERE org_id = %s::uuid AND agent_run_id::text = %s AND outcome IN ('pending', 'planned')
                    ORDER BY id ASC
                    """,
                    (org_id, run_id),
                )
                return [dict(row) for row in cur.fetchall()]

    def mark_action_outcome(self, org_id: str, action_id: str, outcome: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE agent_actions
                    SET outcome = %s
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (outcome, org_id, action_id),
                )


class DocumentsRepository:
    def list_documents(self, org_id: str, doc_type: str | None = None) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if doc_type:
                    cur.execute(
                        """
                        SELECT id::text, title, doc_type, permission_ref, ingested_at
                        FROM documents
                        WHERE org_id = %s::uuid AND doc_type = %s
                        ORDER BY ingested_at DESC
                        """,
                        (org_id, doc_type),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, title, doc_type, permission_ref, ingested_at
                        FROM documents
                        WHERE org_id = %s::uuid
                        ORDER BY ingested_at DESC
                        """,
                        (org_id,),
                    )
                return [dict(row) for row in cur.fetchall()]

    def create_document(
        self,
        org_id: str,
        source_id: str | None,
        external_id: str | None,
        title: str,
        doc_type: str,
        permission_ref: str | None,
    ) -> dict:
        document_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (id, org_id, source_id, external_id, title, doc_type, permission_ref, ingested_at)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, NOW())
                    RETURNING id::text, title, doc_type, permission_ref, ingested_at
                    """,
                    (document_id, org_id, _uuid_or_none(source_id), external_id, title, doc_type, permission_ref),
                )
                return dict(cur.fetchone() or {})

    def create_chunk(
        self,
        org_id: str,
        document_id: str,
        chunk_index: int,
        content: str,
        metadata_jsonb: dict,
        token_count: int,
        embedding: list[float],
    ) -> dict:
        chunk_id = _new_id()
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_chunks (id, org_id, document_id, chunk_index, content, metadata_jsonb, token_count, embedding)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::jsonb, %s, %s::vector)
                    RETURNING id::text, document_id::text, chunk_index
                    """,
                    (chunk_id, org_id, document_id, chunk_index, content, _jsonb(metadata_jsonb), token_count, vector_literal),
                )
                return dict(cur.fetchone() or {})


class RetrievalRepository:
    def search_chunks(
        self,
        org_id: str,
        query_embedding: list[float],
        top_k: int,
        doc_type: str | None = None,
        allowed_source_refs: list[str] | None = None,
    ) -> list[dict]:
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in query_embedding) + "]"
        base_query = """
            SELECT
                dc.id::text AS chunk_id,
                dc.document_id::text AS document_id,
                dc.content,
                dc.metadata_jsonb,
                d.doc_type,
                (dc.embedding <=> %s::vector) AS distance
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.org_id = %s::uuid
        """
        params: list = [vector_literal, org_id]
        if doc_type:
            base_query += " AND d.doc_type = %s"
            params.append(doc_type)
        if isinstance(allowed_source_refs, list) and allowed_source_refs:
            base_query += " AND (d.permission_ref = ANY(%s) OR d.permission_ref IS NULL)"
            params.append(allowed_source_refs)
        base_query += " ORDER BY dc.embedding <=> %s::vector LIMIT %s"
        params.extend([vector_literal, max(top_k, 1)])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(base_query, tuple(params))
                return [dict(row) for row in cur.fetchall()]


class GraphDataRepository:
    def list_workflow_ids(self, org_id: str) -> set[str]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute("SELECT id::text FROM workflows WHERE org_id = %s::uuid", (org_id,))
                return {row["id"] for row in cur.fetchall()}

    def list_invoice_ids(self, org_id: str) -> set[str]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute("SELECT id::text FROM invoices WHERE org_id = %s::uuid", (org_id,))
                return {row["id"] for row in cur.fetchall()}

    def list_invoices_with_vendor(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, COALESCE(vendor_id::text, '') AS vendor_id
                    FROM invoices
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_workflows_with_owner(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id::text AS workflow_id,
                        workflow_type,
                        state,
                        COALESCE(owner_user_id::text, '') AS owner_user_id
                    FROM workflows
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_decisions(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS decision_id, decision_type, title
                    FROM decisions
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_payments_with_invoice(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.id::text AS payment_id, COALESCE(p.invoice_id::text, '') AS invoice_id, p.status
                    FROM payments p
                    WHERE p.org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_purchase_orders_with_vendor(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        po.id::text AS purchase_order_id,
                        po.po_number,
                        COALESCE(po.vendor_id::text, '') AS vendor_id,
                        COALESCE(po.contract_id::text, '') AS contract_id
                    FROM purchase_orders po
                    WHERE po.org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_invoices_with_purchase_order(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        i.id::text AS invoice_id,
                        COALESCE(i.purchase_order_id::text, '') AS purchase_order_id,
                        COALESCE(i.vendor_id::text, '') AS vendor_id
                    FROM invoices i
                    WHERE i.org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_contracts_with_vendor(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.id::text AS contract_id, c.contract_number, COALESCE(c.vendor_id::text, '') AS vendor_id
                    FROM contracts c
                    WHERE c.org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_approvals(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        a.id::text AS approval_id,
                        a.object_type,
                        a.object_id::text AS object_id,
                        COALESCE(a.approver_user_id::text, '') AS approver_user_id,
                        a.status
                    FROM approvals a
                    WHERE a.org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_journal_entries(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS journal_entry_id, period, account_code, status
                    FROM journal_entries
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def _safe_query(self, org_id: str, sql: str) -> list[dict]:
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(sql, (org_id,))
                    return [dict(row) for row in cur.fetchall()]
        except Exception:
            return []

    def list_erp_ap_invoices_with_vendor(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS invoice_id, COALESCE(vendor_id::text, '') AS vendor_id, status
            FROM erp.ap_invoices WHERE org_id = %s::uuid
            """,
        )

    def list_erp_ap_payments_with_allocations(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT p.id::text AS payment_id, a.invoice_id::text AS invoice_id, p.status
            FROM erp.ap_payments p
            JOIN erp.ap_payment_allocations a ON a.payment_id = p.id AND a.org_id = p.org_id
            WHERE p.org_id = %s::uuid
            """,
        )

    def list_erp_ar_invoices_with_customer(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS invoice_id, COALESCE(customer_id::text, '') AS customer_id, status
            FROM erp.ar_invoices WHERE org_id = %s::uuid
            """,
        )

    def list_erp_journals_with_source(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS journal_id, source_type, source_id::text AS source_id, status
            FROM erp.journals WHERE org_id = %s::uuid
            """,
        )

    def list_erp_bank_transactions(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS bank_transaction_id, reference, amount, reconciliation_status
            FROM erp.bank_transactions WHERE org_id = %s::uuid
            """,
        )

    def list_erp_bank_reconciliations(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS reconciliation_id, bank_account_id::text AS bank_account_id, status
            FROM erp.bank_reconciliations WHERE org_id = %s::uuid
            """,
        )

    def list_erp_gst_returns(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS gst_return_id, return_period, status
            FROM erp.gst_returns WHERE org_id = %s::uuid
            """,
        )

    def list_erp_gst_transactions(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS gst_tx_id, source_type, source_id::text AS source_id
            FROM erp.gst_transactions WHERE org_id = %s::uuid
            """,
        )

    def list_erp_assets_with_source(self, org_id: str) -> list[dict]:
        return self._safe_query(
            org_id,
            """
            SELECT id::text AS asset_id, source_invoice_id::text AS source_invoice_id, status
            FROM erp.assets WHERE org_id = %s::uuid AND source_invoice_id IS NOT NULL
            """,
        )


class TrainingEvalRepository:
    def create_qa_gold_example(
        self,
        org_id: str,
        org_scope: str,
        question: str,
        expected_answer: str,
        expected_citations: list[dict],
        tags: list[str],
    ) -> dict:
        example_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO qa_gold_examples (
                        id, org_id, org_scope, question, expected_answer, expected_citations, tags, created_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, NOW())
                    RETURNING id::text, org_scope, question, expected_answer, expected_citations, tags, created_at
                    """,
                    (example_id, org_id, org_scope, question, expected_answer, _jsonb(expected_citations), _jsonb(tags)),
                )
                return dict(cur.fetchone() or {})

    def list_qa_gold_examples(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_scope, question, expected_answer, expected_citations, tags, created_at
                    FROM qa_gold_examples
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def create_retrieval_judgment(
        self,
        org_id: str,
        query: str,
        candidate_ref: str,
        relevance_label: int,
        judged_by: str,
    ) -> dict:
        judgment_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO retrieval_judgments (id, org_id, query, candidate_ref, relevance_label, judged_by, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, NOW())
                    RETURNING id::text, query, candidate_ref, relevance_label, judged_by, created_at
                    """,
                    (judgment_id, org_id, query, candidate_ref, relevance_label, judged_by),
                )
                return dict(cur.fetchone() or {})

    def list_retrieval_judgments(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, query, candidate_ref, relevance_label, judged_by, created_at
                    FROM retrieval_judgments
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def create_safety_event(self, org_id: str, event_type: str, severity: str, request_id: str | None, details: dict) -> dict:
        event_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO safety_events (id, org_id, event_type, severity, request_id, details, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, NOW())
                    RETURNING id::text, event_type, severity, request_id, details, created_at
                    """,
                    (event_id, org_id, event_type, severity, request_id, _jsonb(details)),
                )
                return dict(cur.fetchone() or {})

    def create_feedback_event(self, org_id: str, event_type: str, payload_jsonb: dict, created_by: str) -> dict:
        feedback_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO feedback_events (id, org_id, event_type, payload_jsonb, created_by, created_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s::jsonb, %s, NOW())
                    RETURNING id::text, event_type, payload_jsonb, created_by, created_at
                    """,
                    (feedback_id, org_id, event_type, _jsonb(payload_jsonb), created_by),
                )
                return dict(cur.fetchone() or {})

    def start_eval_run(self, org_id: str, run_type: str) -> dict:
        run_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO eval_runs (id, org_id, run_type, status, metrics_jsonb, started_at, completed_at)
                    VALUES (%s::uuid, %s::uuid, %s, 'running', '{}'::jsonb, NOW(), NULL)
                    RETURNING id::text, run_type, status, metrics_jsonb, started_at, completed_at
                    """,
                    (run_id, org_id, run_type),
                )
                return dict(cur.fetchone() or {})

    def complete_eval_run(self, org_id: str, run_id: str, metrics_jsonb: dict, status: str = "completed") -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE eval_runs
                    SET status = %s, metrics_jsonb = %s::jsonb, completed_at = NOW()
                    WHERE org_id = %s::uuid AND id::text = %s
                    RETURNING id::text, run_type, status, metrics_jsonb, started_at, completed_at
                    """,
                    (status, _jsonb(metrics_jsonb), org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_eval_runs(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, run_type, status, metrics_jsonb, started_at, completed_at
                    FROM eval_runs
                    WHERE org_id = %s::uuid
                    ORDER BY started_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]


class LearningGovernanceRepository:
    def list_feedback_events(self, org_id: str, limit: int = 200) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, event_type, payload_jsonb, created_by, created_at
                    FROM feedback_events
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, max(1, min(limit, 500))),
                )
                return [dict(row) for row in cur.fetchall()]

    def list_untriaged_feedback(self, org_id: str, limit: int = 200) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT f.id::text, f.event_type, f.payload_jsonb, f.created_by, f.created_at
                    FROM feedback_events f
                    LEFT JOIN learning_labeling_tasks t
                        ON t.feedback_event_id = f.id AND t.org_id = f.org_id
                    WHERE f.org_id = %s::uuid AND t.id IS NULL
                    ORDER BY f.created_at DESC
                    LIMIT %s
                    """,
                    (org_id, max(1, min(limit, 500))),
                )
                return [dict(row) for row in cur.fetchall()]

    def create_labeling_task(
        self,
        org_id: str,
        feedback_event_id: str,
        triage_category: str,
        payload_jsonb: dict,
    ) -> dict:
        task_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO learning_labeling_tasks (
                        id, org_id, feedback_event_id, triage_category, status, payload_jsonb, created_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'pending_review', %s::jsonb, NOW())
                    RETURNING id::text, feedback_event_id::text, triage_category, status, payload_jsonb, created_at
                    """,
                    (task_id, org_id, feedback_event_id, triage_category, _jsonb(payload_jsonb)),
                )
                return dict(cur.fetchone() or {})

    def list_labeling_tasks(self, org_id: str, status: str | None = None) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id::text, feedback_event_id::text, triage_category, status, payload_jsonb,
                               reviewer_id, reviewed_at, created_at
                        FROM learning_labeling_tasks
                        WHERE org_id = %s::uuid AND status = %s
                        ORDER BY created_at DESC
                        """,
                        (org_id, status),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, feedback_event_id::text, triage_category, status, payload_jsonb,
                               reviewer_id, reviewed_at, created_at
                        FROM learning_labeling_tasks
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC
                        """,
                        (org_id,),
                    )
                return [dict(row) for row in cur.fetchall()]

    def review_labeling_task(self, org_id: str, task_id: str, reviewer_id: str, status: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE learning_labeling_tasks
                    SET status = %s, reviewer_id = %s, reviewed_at = NOW()
                    WHERE org_id = %s::uuid AND id::text = %s
                    RETURNING id::text, feedback_event_id::text, triage_category, status, payload_jsonb,
                              reviewer_id, reviewed_at, created_at
                    """,
                    (status, reviewer_id, org_id, task_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def create_cycle(self, org_id: str, candidate_version: str, created_by: str, status: str = "feedback_triage") -> dict:
        cycle_id = _new_id()
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO learning_governance_cycles (
                        id, org_id, candidate_version, status, promotion_decision, canary_percent,
                        metrics_jsonb, created_by, created_at, updated_at
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, 'pending', 0, '{}'::jsonb, %s, NOW(), NOW())
                    RETURNING id::text, candidate_version, status, promotion_decision, canary_percent,
                              metrics_jsonb, created_by, created_at, updated_at
                    """,
                    (cycle_id, org_id, candidate_version, status, created_by),
                )
                return dict(cur.fetchone() or {})

    def get_cycle(self, org_id: str, cycle_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, candidate_version, status, baseline_eval_run_id::text,
                           shadow_eval_run_id::text, promotion_decision, governance_approver,
                           canary_percent, metrics_jsonb, created_by, created_at, updated_at
                    FROM learning_governance_cycles
                    WHERE org_id = %s::uuid AND id::text = %s
                    """,
                    (org_id, cycle_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_cycles(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, candidate_version, status, promotion_decision, canary_percent,
                           metrics_jsonb, created_by, created_at, updated_at
                    FROM learning_governance_cycles
                    WHERE org_id = %s::uuid
                    ORDER BY updated_at DESC
                    """,
                    (org_id,),
                )
                return [dict(row) for row in cur.fetchall()]

    def update_cycle(
        self,
        org_id: str,
        cycle_id: str,
        status: str | None = None,
        baseline_eval_run_id: str | None = None,
        shadow_eval_run_id: str | None = None,
        promotion_decision: str | None = None,
        governance_approver: str | None = None,
        canary_percent: int | None = None,
        metrics_jsonb: dict | None = None,
    ) -> dict | None:
        cycle = self.get_cycle(org_id=org_id, cycle_id=cycle_id)
        if not cycle:
            return None
        next_status = status or cycle["status"]
        next_decision = promotion_decision or cycle["promotion_decision"]
        next_canary = canary_percent if canary_percent is not None else int(cycle.get("canary_percent") or 0)
        next_metrics = metrics_jsonb if metrics_jsonb is not None else cycle.get("metrics_jsonb", {})
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE learning_governance_cycles
                    SET status = %s,
                        baseline_eval_run_id = COALESCE(%s::uuid, baseline_eval_run_id),
                        shadow_eval_run_id = COALESCE(%s::uuid, shadow_eval_run_id),
                        promotion_decision = %s,
                        governance_approver = COALESCE(%s, governance_approver),
                        canary_percent = %s,
                        metrics_jsonb = %s::jsonb,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id::text = %s
                    RETURNING id::text, candidate_version, status, baseline_eval_run_id::text,
                              shadow_eval_run_id::text, promotion_decision, governance_approver,
                              canary_percent, metrics_jsonb, created_by, created_at, updated_at
                    """,
                    (
                        next_status,
                        _uuid_or_none(baseline_eval_run_id),
                        _uuid_or_none(shadow_eval_run_id),
                        next_decision,
                        governance_approver,
                        next_canary,
                        _jsonb(next_metrics),
                        org_id,
                        cycle_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def latest_eval_run(self, org_id: str, run_type: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, run_type, status, metrics_jsonb, started_at, completed_at
                    FROM eval_runs
                    WHERE org_id = %s::uuid AND run_type = %s AND status = 'completed'
                    ORDER BY completed_at DESC NULLS LAST, started_at DESC
                    LIMIT 1
                    """,
                    (org_id, run_type),
                )
                row = cur.fetchone()
                return dict(row) if row else None


sources_repo = SourcesRepository()
ingestion_repo = IngestionRepository()
workflows_repo = WorkflowsRepository()
decisions_repo = DecisionsRepository()
memory_repo = MemoryRepository()
audit_repo = AuditRepository()
agents_repo = AgentsRepository()
invoices_repo = InvoicesRepository()
canonical_repo = CanonicalRepository()
documents_repo = DocumentsRepository()
graph_data_repo = GraphDataRepository()
retrieval_repo = RetrievalRepository()
training_eval_repo = TrainingEvalRepository()
learning_governance_repo = LearningGovernanceRepository()
