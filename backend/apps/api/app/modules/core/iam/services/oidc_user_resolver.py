"""Resolve or JIT-provision users from OIDC ID token claims."""

from __future__ import annotations

from app.core.config import settings
from app.modules.core.iam.repositories import role_repo, user_repo
from app.modules.core.iam.services.password_service import hash_password
import secrets


def _claim(claims: dict, key: str, fallback: str = "") -> str:
    return str(claims.get(key) or fallback).strip()


def resolve_oidc_user(claims: dict) -> dict | None:
    idp_subject = _claim(claims, "sub")
    idp_provider = settings.oidc_provider or "oidc"
    email = _claim(claims, "email").lower()
    org_claim = _claim(claims, settings.oidc_org_claim) or _claim(claims, settings.jwt_tenant_claim)

    user = None
    if idp_subject:
        user = user_repo.get_by_idp_subject(idp_provider, idp_subject)
    if not user and email:
        user = user_repo.get_by_email(email)
    if not user and email and settings.oidc_jit_provisioning_enabled and org_claim:
        user = _jit_provision(org_claim, email, claims, idp_provider, idp_subject)
    elif user and idp_subject and not user.get("idp_subject"):
        user_repo.link_idp_subject(user["org_id"], user["id"], idp_provider, idp_subject)
        user["idp_subject"] = idp_subject
        user["idp_provider"] = idp_provider

    if not user or user.get("status") != "active":
        return None
    return user


def _jit_provision(
    org_id: str,
    email: str,
    claims: dict,
    idp_provider: str,
    idp_subject: str,
) -> dict | None:
    display_name = _claim(claims, "name") or _claim(claims, "preferred_username") or email.split("@")[0]
    random_password = secrets.token_urlsafe(32)
    created = user_repo.create_user(
        org_id=org_id,
        email=email,
        display_name=display_name,
        password_hash=hash_password(random_password),
    )
    user_repo.link_idp_subject(org_id, created["id"], idp_provider, idp_subject)
    default_role = settings.oidc_jit_default_role.strip()
    if default_role:
        role = role_repo.get_role_by_name(org_id, default_role)
        if role:
            user_repo.assign_role(org_id, created["id"], role["id"])
    return user_repo.get_by_id(org_id, created["id"])
