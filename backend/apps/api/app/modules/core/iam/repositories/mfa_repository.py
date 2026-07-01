import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class MfaRepository:
    def get_method(self, org_id: str, user_id: str, method: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, method, enabled, metadata
                    FROM core.user_mfa_methods
                    WHERE org_id = %s::uuid AND user_id = %s::uuid AND method = %s
                    """,
                    (org_id, user_id, method),
                )
                return cur.fetchone()

    def list_enabled_methods(self, org_id: str, user_id: str) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT method, enabled, metadata
                    FROM core.user_mfa_methods
                    WHERE org_id = %s::uuid AND user_id = %s::uuid AND enabled = TRUE
                    """,
                    (org_id, user_id),
                )
                return list(cur.fetchall())

    def upsert_method(
        self,
        org_id: str,
        user_id: str,
        method: str,
        *,
        enabled: bool = False,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.user_mfa_methods (org_id, user_id, method, enabled, metadata)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                    ON CONFLICT (user_id, method) DO UPDATE SET
                        enabled = EXCLUDED.enabled,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    RETURNING id::text AS id, method, enabled, metadata
                    """,
                    (org_id, user_id, method, enabled, Json(metadata or {})),
                )
                return cur.fetchone()

    def disable_all_methods(self, org_id: str, user_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.user_mfa_methods SET enabled = FALSE, updated_at = NOW()
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                    """,
                    (org_id, user_id),
                )
                cur.execute(
                    "UPDATE core.users SET mfa_enabled = FALSE, mfa_secret = NULL, updated_at = NOW() WHERE id = %s::uuid",
                    (user_id,),
                )
                return cur.rowcount

    def register_device(
        self,
        org_id: str,
        user_id: str,
        fingerprint: str,
        device_name: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.user_devices (org_id, user_id, fingerprint, device_name, last_seen_at)
                    VALUES (%s::uuid, %s::uuid, %s, %s, NOW())
                    ON CONFLICT (user_id, fingerprint) DO UPDATE SET
                        device_name = COALESCE(EXCLUDED.device_name, core.user_devices.device_name),
                        last_seen_at = NOW()
                    RETURNING id::text AS id, fingerprint, device_name, last_seen_at, registered_at
                    """,
                    (org_id, user_id, fingerprint, device_name),
                )
                return cur.fetchone()

    def trust_device(
        self,
        org_id: str,
        user_id: str,
        device_id: str,
        *,
        trust_days: int = 30,
    ) -> dict[str, Any]:
        expires = datetime.now(timezone.utc) + timedelta(days=trust_days)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.trusted_devices (org_id, user_id, device_id, trust_expires_at, mfa_skip_until)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s)
                    ON CONFLICT (user_id, device_id) DO UPDATE SET
                        trust_expires_at = EXCLUDED.trust_expires_at,
                        mfa_skip_until = EXCLUDED.mfa_skip_until
                    RETURNING id::text AS id, device_id::text AS device_id, trust_expires_at, mfa_skip_until
                    """,
                    (org_id, user_id, device_id, expires, expires),
                )
                return cur.fetchone()

    def is_device_trusted(self, org_id: str, user_id: str, fingerprint: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM core.trusted_devices td
                    JOIN core.user_devices ud ON ud.id = td.device_id
                    WHERE td.org_id = %s::uuid AND td.user_id = %s::uuid
                      AND ud.fingerprint = %s
                      AND td.trust_expires_at > NOW()
                    LIMIT 1
                    """,
                    (org_id, user_id, fingerprint),
                )
                return cur.fetchone() is not None

    def revoke_trusted_devices(self, org_id: str, user_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM core.trusted_devices WHERE org_id = %s::uuid AND user_id = %s::uuid",
                    (org_id, user_id),
                )
                return cur.rowcount

    def store_recovery_codes(self, org_id: str, user_id: str, code_hashes: list[str], batch_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM core.recovery_codes WHERE user_id = %s::uuid AND used_at IS NULL",
                    (user_id,),
                )
                for code_hash in code_hashes:
                    cur.execute(
                        """
                        INSERT INTO core.recovery_codes (org_id, user_id, code_hash, batch_id)
                        VALUES (%s::uuid, %s::uuid, %s, %s::uuid)
                        """,
                        (org_id, user_id, code_hash, batch_id),
                    )

    def consume_recovery_code(self, org_id: str, user_id: str, code_hash: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.recovery_codes
                    SET used_at = NOW()
                    WHERE org_id = %s::uuid AND user_id = %s::uuid
                      AND code_hash = %s AND used_at IS NULL
                    RETURNING id
                    """,
                    (org_id, user_id, code_hash),
                )
                return cur.fetchone() is not None

    def get_org_security_policy(self, org_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT required_methods, grace_period_days, webauthn_required_for_admins,
                           max_concurrent_sessions
                    FROM core.org_security_policy
                    WHERE org_id = %s::uuid
                    """,
                    (org_id,),
                )
                return cur.fetchone()

    @staticmethod
    def hash_recovery_code(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_recovery_codes(count: int = 10) -> list[str]:
        return [secrets.token_hex(4).upper() for _ in range(count)]


mfa_repo = MfaRepository()
