import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_SCHEMA_PROBE_ATTEMPTS = 3


class IamSchemaError(Exception):
    pass


def _probe_core_users_table() -> tuple[bool, Exception | None]:
    from app.services.db import get_db_conn

    last_error: Exception | None = None
    for attempt in range(1, _SCHEMA_PROBE_ATTEMPTS + 1):
        try:
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
                    return bool(row and row.get("ok")), None
        except Exception as exc:
            last_error = exc
            logger.warning(
                "IAM schema probe attempt %s/%s failed: %s",
                attempt,
                _SCHEMA_PROBE_ATTEMPTS,
                exc,
            )
    return False, last_error


def core_schema_ready() -> bool:
    if not settings.postgres_dsn:
        return False
    from app.services.schema_registry import is_core_ready

    return is_core_ready()


def require_core_schema() -> None:
    if not settings.postgres_dsn:
        raise IamSchemaError("POSTGRES_DSN is required for IAM database authentication")
    if not settings.iam_use_db_auth:
        return

    from app.services.schema_registry import is_core_ready

    if is_core_ready():
        return
    ready, last_error = _probe_core_users_table()
    if ready:
        from app.services.schema_registry import set_core_ready

        set_core_ready(True)
        return
    if last_error is not None:
        raise IamSchemaError(
            f"Database connection unavailable for IAM authentication: {last_error}"
        ) from last_error
    raise IamSchemaError(
        "IAM core schema not ready. Run migrations 009_core_iam.sql and 010+ before enabling IAM_USE_DB_AUTH."
    )
