import jwt

from app.core.config import settings
from app.services.redis_client import get_redis_client


def _revocation_key(jti: str) -> str:
    return f"{settings.oidc_store_prefix}:revoke:{jti}"


def revoke_access_token_jti(access_token: str) -> None:
    if not access_token.strip():
        return
    try:
        payload = jwt.decode(
            access_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"verify_exp": False},
        )
    except Exception:
        return
    jti = str(payload.get("jti", "")).strip()
    exp = payload.get("exp")
    if not jti:
        return
    ttl = 3600
    if isinstance(exp, (int, float)):
        ttl = max(60, int(exp) - int(__import__("time").time()))
    client = get_redis_client()
    if not client:
        return
    try:
        client.setex(_revocation_key(jti), ttl, "1")
    except Exception:
        pass
