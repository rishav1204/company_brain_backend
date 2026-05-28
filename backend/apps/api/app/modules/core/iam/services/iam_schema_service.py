from app.core.config import settings


class IamSchemaError(Exception):
    pass


def core_schema_ready() -> bool:
    if not settings.postgres_dsn:
        return False
    try:
        from app.services.db import get_db_conn

        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'core' AND table_name = 'users'
                    ) AS ok
                    """
                )
                row = cur.fetchone()
                return bool(row and row.get("ok"))
    except Exception:
        return False


def require_core_schema() -> None:
    if not settings.postgres_dsn:
        raise IamSchemaError("POSTGRES_DSN is required for IAM database authentication")
    if settings.iam_use_db_auth and not core_schema_ready():
        raise IamSchemaError(
            "IAM core schema not ready. Run migrations 009_core_iam.sql and 010+ before enabling IAM_USE_DB_AUTH."
        )
