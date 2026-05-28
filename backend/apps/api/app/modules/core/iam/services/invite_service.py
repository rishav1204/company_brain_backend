import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.modules.core.iam.events.user_events import emit_user_created, emit_user_invited
from app.modules.core.iam.repositories import role_repo, user_repo
from app.modules.core.iam.services.password_service import hash_password
from app.modules.core.iam.validators.password_validator import validate_password_strength
from app.services.db import get_db_conn, set_rls_org

INVITE_TTL_HOURS = 72


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_invite(
    *,
    org_id: str,
    email: str,
    role_name: str,
    invited_by: str,
    trace_id: str,
    company_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    role = role_repo.get_role_by_name(org_id, role_name)
    if not role:
        raise ValueError("Role not found")
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO core.user_invites (
                    org_id, email, role_id, company_id, branch_id,
                    token_hash, expires_at, invited_by, status
                )
                VALUES (%s::uuid, %s, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid, 'pending')
                RETURNING id::text AS id, email, expires_at
                """,
                (
                    org_id,
                    email.strip().lower(),
                    role["id"],
                    company_id,
                    branch_id,
                    _hash_token(raw_token),
                    expires_at,
                    invited_by,
                ),
            )
            row = cur.fetchone()
    emit_user_invited(org_id=org_id, invite_id=row["id"], email=row["email"], trace_id=trace_id)
    return {"invite_id": row["id"], "email": row["email"], "invite_token": raw_token, "expires_at": row["expires_at"]}


def accept_invite(*, invite_token: str, password: str, display_name: str, trace_id: str) -> dict:
    validate_password_strength(password)
    token_hash = _hash_token(invite_token)
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text AS id, org_id::text AS org_id, email, role_id::text AS role_id,
                       company_id::text AS company_id, branch_id::text AS branch_id, expires_at, status
                FROM core.user_invites
                WHERE token_hash = %s AND status = 'pending'
                LIMIT 1
                """,
                (token_hash,),
            )
            invite = cur.fetchone()
    if not invite:
        raise ValueError("Invalid or expired invite")
    if invite["expires_at"] < datetime.now(timezone.utc):
        raise ValueError("Invite expired")

    org_id = invite["org_id"]
    user = user_repo.create_user(
        org_id=org_id,
        email=invite["email"],
        display_name=display_name,
        password_hash=hash_password(password),
    )
    user_repo.assign_role(
        org_id=org_id,
        user_id=user["id"],
        role_id=invite["role_id"],
        company_id=invite.get("company_id"),
        branch_id=invite.get("branch_id"),
    )
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE core.user_invites
                SET status = 'accepted', accepted_at = NOW()
                WHERE id = %s::uuid
                """,
                (invite["id"],),
            )
    emit_user_created(org_id=org_id, user_id=user["id"], email=user["email"], trace_id=trace_id)
    return user
