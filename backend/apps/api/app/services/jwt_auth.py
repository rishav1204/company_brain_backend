from dataclasses import dataclass
from time import time

import jwt
from jwt import InvalidTokenError
from jwt import PyJWKClient

from app.core.config import settings
from app.services.redis_client import get_redis_client


@dataclass
class JwtPrincipal:
    user_id: str
    org_id: str
    roles: list[str]
    source_acl: list[str]
    attrs: dict
    raw_claims: dict
    permissions: list[str] | None = None
    session_id: str | None = None


def _revocation_key(jti: str) -> str:
    return f"{settings.oidc_store_prefix}:revoke:{jti}"


def _is_token_revoked(jti: str) -> bool:
    if not jti.strip():
        return False
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.get(_revocation_key(jti)))
    except Exception:
        if settings.jwt_revocation_fail_closed and settings.app_env.lower() == "prod":
            return True
        return False


def decode_bearer_token(token: str) -> JwtPrincipal:
    if settings.app_env.lower() == "prod" and settings.jwt_require_jwks_in_prod and not settings.jwt_jwks_url:
        raise InvalidTokenError("JWT_JWKS_URL must be configured in production")
    decode_kwargs = {
        "algorithms": [settings.jwt_algorithm],
        "audience": settings.jwt_audience,
        "issuer": settings.jwt_issuer,
        "options": {"require": ["exp"] if settings.jwt_require_exp else []},
    }
    if settings.jwt_jwks_url:
        jwks_client = PyJWKClient(settings.jwt_jwks_url, cache_keys=True, lifespan=300)
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(token, signing_key, **decode_kwargs)
    else:
        if settings.app_env.lower() == "prod" and settings.jwt_require_jwks_in_prod:
            raise InvalidTokenError("Symmetric JWT verification is disabled in production")
        payload = jwt.decode(token, settings.jwt_secret, **decode_kwargs)

    exp = payload.get("exp")
    if settings.jwt_require_exp and (not isinstance(exp, (int, float)) or exp <= int(time())):
        raise InvalidTokenError("Token is expired")
    jti = str(payload.get("jti", "")).strip()
    if jti and _is_token_revoked(jti):
        raise InvalidTokenError("Token has been revoked")
    org_id = payload.get(settings.jwt_tenant_claim)
    user_id = payload.get(settings.jwt_user_claim)
    roles = payload.get(settings.jwt_roles_claim, [])
    if not isinstance(roles, list):
        roles = [str(roles)]
    source_acl = payload.get("source_acl", [])
    if not isinstance(source_acl, list):
        source_acl = [str(source_acl)]
    attrs = payload.get("attrs", {})
    if not isinstance(attrs, dict):
        attrs = {}
    permissions = payload.get("permissions", [])
    if not isinstance(permissions, list):
        permissions = [str(permissions)]
    session_id = payload.get("session_id")
    session_id_str = str(session_id) if session_id else None

    if not org_id or not user_id:
        raise InvalidTokenError("Required claims missing")

    return JwtPrincipal(
        user_id=str(user_id),
        org_id=str(org_id),
        roles=[str(role) for role in roles if str(role).strip()],
        source_acl=[str(item) for item in source_acl if str(item).strip()],
        attrs=attrs,
        raw_claims=payload,
        permissions=[str(p) for p in permissions if str(p).strip()],
        session_id=session_id_str,
    )
