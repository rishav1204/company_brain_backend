import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
import redis
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import settings


def _urlsafe(n_bytes: int = 32) -> str:
    return secrets.token_urlsafe(n_bytes)


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


@dataclass
class OidcState:
    state: str
    nonce: str
    code_verifier: str | None
    redirect_uri: str
    created_at: float


class OidcService:
    def __init__(self) -> None:
        self.client: redis.Redis | None = None
        redis_url = settings.redis_url.strip()
        if redis_url:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def _state_key(self, state: str) -> str:
        return f"{settings.oidc_store_prefix}:state:{state}"

    def _refresh_key(self, refresh_token_id: str) -> str:
        return f"{settings.oidc_store_prefix}:refresh:{refresh_token_id}"

    def _revoke_key(self, jti: str) -> str:
        return f"{settings.oidc_store_prefix}:revoke:{jti}"

    def _prod_jwks_mode(self) -> bool:
        return settings.app_env.lower() == "prod" and settings.jwt_require_jwks_in_prod

    def is_enabled(self) -> bool:
        return settings.oidc_enabled

    def start_authorize(self, redirect_uri: str | None = None) -> dict:
        if not settings.oidc_enabled:
            raise ValueError("OIDC is disabled")
        if not settings.oidc_authorization_endpoint:
            raise ValueError("OIDC_AUTHORIZATION_ENDPOINT is required")
        if not settings.oidc_client_id:
            raise ValueError("OIDC_CLIENT_ID is required")
        effective_redirect = redirect_uri or settings.oidc_redirect_uri
        if not effective_redirect:
            raise ValueError("OIDC redirect URI is required")

        state = _urlsafe(24)
        nonce = _urlsafe(24)
        code_verifier = _urlsafe(48) if settings.oidc_use_pkce else None
        record = OidcState(
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
            redirect_uri=effective_redirect,
            created_at=time.time(),
        )
        self.client.setex(self._state_key(state), max(60, settings.oidc_state_ttl_seconds), json.dumps(record.__dict__))
        query = {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": effective_redirect,
            "scope": settings.oidc_scopes,
            "state": state,
            "nonce": nonce,
        }
        if settings.oidc_use_pkce and code_verifier:
            query["code_challenge"] = _challenge(code_verifier)
            query["code_challenge_method"] = "S256"
        authorize_url = f"{settings.oidc_authorization_endpoint}?{urlencode(query)}"
        return {"authorize_url": authorize_url, "state": state}

    def callback_exchange(self, code: str, state: str) -> dict:
        if not settings.oidc_enabled:
            raise ValueError("OIDC is disabled")
        if not settings.oidc_token_endpoint:
            raise ValueError("OIDC_TOKEN_ENDPOINT is required")
        if not settings.oidc_client_id:
            raise ValueError("OIDC_CLIENT_ID is required")
        if not settings.oidc_client_secret:
            raise ValueError("OIDC_CLIENT_SECRET is required")

        saved_raw = self.client.get(self._state_key(state))
        self.client.delete(self._state_key(state))
        if not saved_raw:
            raise ValueError("Invalid or expired OIDC state")
        saved = OidcState(**json.loads(saved_raw))
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": saved.redirect_uri,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        }
        if settings.oidc_use_pkce and saved.code_verifier:
            body["code_verifier"] = saved.code_verifier
        response = httpx.post(settings.oidc_token_endpoint, data=body, timeout=15.0)
        if response.status_code < 200 or response.status_code >= 300:
            raise ValueError(f"OIDC token exchange failed: http_{response.status_code}")
        payload = response.json()
        id_token = str(payload.get("id_token", "")).strip()
        access_token = str(payload.get("access_token", "")).strip()
        if not id_token:
            raise ValueError("OIDC response missing id_token")
        claims = self.validate_id_token(id_token=id_token, expected_nonce=saved.nonce)
        refresh_token = str(payload.get("refresh_token", "")).strip()
        return {
            "id_token": id_token,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "claims": claims,
        }

    def validate_id_token(self, id_token: str, expected_nonce: str | None = None) -> dict:
        issuer = settings.oidc_issuer or settings.jwt_issuer
        audience = settings.oidc_client_id or settings.jwt_audience
        options = {"require": ["exp", "iat", "iss", "aud", "sub"]}
        if settings.oidc_jwks_url:
            jwks = PyJWKClient(settings.oidc_jwks_url, cache_keys=True, lifespan=300)
            key = jwks.get_signing_key_from_jwt(id_token).key
            claims = jwt.decode(
                id_token,
                key,
                algorithms=[settings.jwt_algorithm],
                issuer=issuer,
                audience=audience,
                options=options,
            )
        elif settings.jwt_jwks_url:
            jwks = PyJWKClient(settings.jwt_jwks_url, cache_keys=True, lifespan=300)
            key = jwks.get_signing_key_from_jwt(id_token).key
            claims = jwt.decode(
                id_token,
                key,
                algorithms=[settings.jwt_algorithm],
                issuer=issuer,
                audience=audience,
                options=options,
            )
        else:
            raise InvalidTokenError("OIDC JWKS URL is required for ID token validation")
        nonce = claims.get("nonce")
        if expected_nonce and nonce != expected_nonce:
            raise InvalidTokenError("OIDC nonce mismatch")
        return claims

    def issue_api_session(
        self,
        claims: dict,
        include_refresh: bool = True,
        upstream_access_token: str | None = None,
        upstream_id_token: str | None = None,
        provider_refresh_token: str | None = None,
    ) -> dict:
        user_id = str(claims.get(settings.oidc_user_claim) or claims.get("sub") or "").strip()
        org_id = str(claims.get(settings.oidc_org_claim) or "").strip()
        roles = claims.get(settings.oidc_roles_claim, [])
        if not isinstance(roles, list):
            roles = [str(roles)]
        if not user_id or not org_id:
            raise ValueError("OIDC claims missing org_id/sub")
        if self._prod_jwks_mode():
            # In production, API session token must be verifiable via runtime JWKS policy.
            from app.services.jwt_auth import decode_bearer_token

            runtime_token = ""
            for candidate in [upstream_access_token or "", upstream_id_token or ""]:
                if not candidate:
                    continue
                try:
                    principal = decode_bearer_token(candidate)
                except Exception:
                    continue
                runtime_token = candidate
                org_id = principal.org_id
                user_id = principal.user_id
                roles = principal.roles
                break
            if not runtime_token:
                raise ValueError("OIDC upstream token is not compatible with API JWT verification policy")

            now_ts = int(time.time())
            exp = claims.get("exp")
            if isinstance(exp, (int, float)):
                expires_in = max(1, int(exp) - now_ts)
            else:
                expires_in = max(300, settings.api_session_ttl_seconds)
            response = {
                "access_token": runtime_token,
                "expires_in": expires_in,
                "org_id": org_id,
                "user_id": user_id,
                "jti": str(claims.get("jti", "")).strip(),
            }
            if include_refresh and provider_refresh_token:
                refresh_token_id = _urlsafe(24)
                refresh_token = _urlsafe(48)
                self.client.setex(
                    self._refresh_key(refresh_token_id),
                    max(3600, settings.oidc_refresh_ttl_seconds),
                    json.dumps({"refresh_token": refresh_token, "provider_refresh_token": provider_refresh_token}),
                )
                response["refresh_token"] = f"{refresh_token_id}.{refresh_token}"
            return response

        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=max(300, settings.api_session_ttl_seconds))
        token_roles = [str(role) for role in roles if str(role).strip()]
        token_attrs = claims.get("attrs", {})
        if not isinstance(token_attrs, dict):
            token_attrs = {}
        token_permissions: list[str] = []
        try:
            from app.modules.core.iam.services.auth_service import iam_db_enabled

            if iam_db_enabled():
                from app.modules.core.iam.repositories import permission_repo, user_repo
                from app.modules.core.iam.services.rbac_service import list_role_names, merge_policy_context

                db_user = user_repo.get_by_id(org_id, user_id)
                if db_user:
                    db_roles = list_role_names(org_id, user_id)
                    if db_roles:
                        token_roles = db_roles
                    token_attrs = merge_policy_context(org_id, user_id)
                    token_permissions = permission_repo.list_permissions_for_user(org_id, user_id)
        except Exception:
            pass
        token_payload = {
            settings.jwt_tenant_claim: org_id,
            settings.jwt_user_claim: user_id,
            settings.jwt_roles_claim: token_roles,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "source_acl": claims.get("source_acl", []),
            "attrs": token_attrs,
            "permissions": token_permissions,
            "amr": ["oidc"],
            "jti": _urlsafe(18),
        }
        token = jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        response = {
            "access_token": token,
            "expires_in": int(exp.timestamp() - now.timestamp()),
            "org_id": org_id,
            "user_id": user_id,
            "jti": token_payload["jti"],
        }
        if include_refresh:
            refresh_token_id = _urlsafe(24)
            refresh_token = _urlsafe(48)
            self.client.setex(
                self._refresh_key(refresh_token_id),
                max(3600, settings.oidc_refresh_ttl_seconds),
                json.dumps({"refresh_token": refresh_token, "claims": claims}),
            )
            response["refresh_token"] = f"{refresh_token_id}.{refresh_token}"
        return response

    def refresh_api_session(self, refresh_token: str) -> dict:
        token_id, _, token_secret = refresh_token.partition(".")
        if not token_id or not token_secret:
            raise ValueError("Malformed refresh token")
        raw = self.client.get(self._refresh_key(token_id))
        if not raw:
            raise ValueError("Refresh token not found or expired")
        payload = json.loads(raw)
        if payload.get("refresh_token") != token_secret:
            raise ValueError("Refresh token mismatch")
        provider_refresh_token = str(payload.get("provider_refresh_token", "")).strip()
        if self._prod_jwks_mode():
            if not provider_refresh_token:
                raise ValueError("Provider refresh token is required in production")
            if not settings.oidc_token_endpoint:
                raise ValueError("OIDC_TOKEN_ENDPOINT is required")
            if not settings.oidc_client_id or not settings.oidc_client_secret:
                raise ValueError("OIDC client credentials are required")
            response = httpx.post(
                settings.oidc_token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": provider_refresh_token,
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret,
                },
                timeout=15.0,
            )
            if response.status_code < 200 or response.status_code >= 300:
                raise ValueError(f"OIDC refresh exchange failed: http_{response.status_code}")
            token_payload = response.json()
            id_token = str(token_payload.get("id_token", "")).strip()
            access_token = str(token_payload.get("access_token", "")).strip()
            if not id_token:
                raise ValueError("OIDC refresh missing id_token")
            claims = self.validate_id_token(id_token=id_token, expected_nonce=None)
            next_provider_refresh = str(token_payload.get("refresh_token", "")).strip() or provider_refresh_token
            session = self.issue_api_session(
                claims=claims,
                include_refresh=False,
                upstream_access_token=access_token,
                upstream_id_token=id_token,
                provider_refresh_token=next_provider_refresh,
            )
            self.client.setex(
                self._refresh_key(token_id),
                max(3600, settings.oidc_refresh_ttl_seconds),
                json.dumps({"refresh_token": token_secret, "provider_refresh_token": next_provider_refresh}),
            )
            return session
        claims = payload.get("claims", {})
        return self.issue_api_session(claims=claims, include_refresh=False)

    def revoke_access_token(self, access_token: str) -> None:
        decoded = jwt.decode(
            access_token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        jti = str(decoded.get("jti", "")).strip()
        exp = int(decoded.get("exp", int(time.time()) + 60))
        ttl = max(60, exp - int(time.time()))
        if jti:
            self.client.setex(self._revoke_key(jti), ttl, "1")

    def logout(self, refresh_token: str | None = None, access_token: str | None = None) -> None:
        if refresh_token:
            token_id, _, _ = refresh_token.partition(".")
            if token_id:
                self.client.delete(self._refresh_key(token_id))
        if access_token:
            self.revoke_access_token(access_token)


oidc_service = OidcService()
