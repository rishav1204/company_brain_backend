"""IAM-integrated OIDC service — unified sessions via core.sessions."""

from __future__ import annotations

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
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import settings
from app.services.redis_client import get_redis_client


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


class IamOidcService:
    def __init__(self) -> None:
        self.client = get_redis_client()

    def _state_key(self, state: str) -> str:
        return f"{settings.oidc_store_prefix}:state:{state}"

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
        allowed = [u.strip() for u in settings.oidc_allowed_redirect_uris.split(",") if u.strip()]
        if allowed and effective_redirect not in allowed:
            raise ValueError("redirect_uri is not in OIDC_ALLOWED_REDIRECT_URIS")

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
        if not settings.oidc_client_id or not settings.oidc_client_secret:
            raise ValueError("OIDC client credentials are required")

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
        if not id_token:
            raise ValueError("OIDC response missing id_token")
        claims = self.validate_id_token(id_token=id_token, expected_nonce=saved.nonce)
        return {
            "id_token": id_token,
            "access_token": str(payload.get("access_token", "")).strip(),
            "refresh_token": str(payload.get("refresh_token", "")).strip(),
            "claims": claims,
        }

    def validate_id_token(self, id_token: str, expected_nonce: str | None = None) -> dict:
        issuer = settings.oidc_issuer or settings.jwt_issuer
        audience = settings.oidc_client_id or settings.jwt_audience
        options = {"require": ["exp", "iat", "iss", "aud", "sub"]}
        jwks_url = settings.oidc_jwks_url or settings.jwt_jwks_url
        if not jwks_url:
            raise InvalidTokenError("OIDC JWKS URL is required for ID token validation")
        jwks = PyJWKClient(jwks_url, cache_keys=True, lifespan=300)
        key = jwks.get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(
            id_token,
            key,
            algorithms=[settings.jwt_algorithm],
            issuer=issuer,
            audience=audience,
            options=options,
        )
        nonce = claims.get("nonce")
        if expected_nonce and nonce != expected_nonce:
            raise InvalidTokenError("OIDC nonce mismatch")
        return claims

    def complete_login(
        self,
        claims: dict,
        *,
        device_info: dict | None = None,
        ip_address: str | None = None,
        mfa_code: str | None = None,
        device_fingerprint: str | None = None,
        trust_device: bool = False,
    ) -> dict:
        """Resolve IdP user, create core.sessions, issue IAM access token."""
        from app.modules.core.iam.services.auth_service import AuthError, iam_db_enabled

        if not iam_db_enabled():
            return self._legacy_token_session(claims)

        from app.modules.core.iam.repositories import permission_repo, user_repo
        from app.modules.core.iam.services.auth_audit_service import record_auth_event
        from app.modules.core.iam.services.device_trust_service import trust_device_for_user
        from app.modules.core.iam.services.jwt_service import issue_access_token
        from app.modules.core.iam.services.mfa_service import MfaRequired, assert_mfa_gate
        from app.modules.core.iam.services.oidc_user_resolver import resolve_oidc_user
        from app.modules.core.iam.services.rbac_service import list_role_names, merge_policy_context
        from app.modules.core.iam.services.session_policy_service import enforce_concurrent_session_limit
        from app.modules.core.iam.services.session_service import create_refresh_session

        user = resolve_oidc_user(claims)
        if not user:
            raise AuthError("OIDC user could not be resolved or provisioned")

        org_id = user["org_id"]
        user_id = user["id"]
        roles = list_role_names(org_id, user_id)
        if not roles:
            raise AuthError("No roles assigned")
        permissions = permission_repo.list_permissions_for_user(org_id, user_id)
        attrs = merge_policy_context(org_id, user_id)
        attrs["amr"] = ["oidc"]
        try:
            assert_mfa_gate(
                org_id=org_id,
                user_id=user_id,
                attrs=attrs,
                mfa_code=mfa_code,
                device_fingerprint=device_fingerprint,
            )
        except MfaRequired as exc:
            raise AuthError(str(exc)) from exc

        enforce_concurrent_session_limit(org_id, user_id)
        raw_refresh, session_id = create_refresh_session(
            org_id=org_id,
            user_id=user_id,
            device_info=device_info,
            ip_address=ip_address,
        )
        access_token, expires_in = issue_access_token(
            user_id=user_id,
            org_id=org_id,
            roles=roles,
            permissions=permissions,
            session_id=session_id,
            attrs=attrs,
            email=user.get("email"),
        )
        user_repo.update_last_login(user_id)

        if trust_device and device_fingerprint:
            trust_device_for_user(org_id, user_id, device_fingerprint, device_info)

        record_auth_event(
            event="oidc_login",
            success=True,
            org_id=org_id,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=(device_info or {}).get("user_agent"),
            metadata={"idp_provider": settings.oidc_provider},
        )
        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "expires_in": expires_in,
            "user_id": user_id,
            "org_id": org_id,
            "roles": roles,
            "permissions": permissions,
        }

    def _legacy_token_session(self, claims: dict) -> dict:
        """Non-IAM fallback for legacy OIDC token issuance."""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(seconds=max(300, settings.api_session_ttl_seconds))
        org_id = str(claims.get(settings.oidc_org_claim) or claims.get(settings.jwt_tenant_claim) or "")
        user_id = str(claims.get(settings.oidc_user_claim) or claims.get("sub") or "")
        roles = claims.get(settings.oidc_roles_claim, [])
        if not isinstance(roles, list):
            roles = [str(roles)]
        token_payload = {
            settings.jwt_tenant_claim: org_id,
            settings.jwt_user_claim: user_id,
            settings.jwt_roles_claim: [str(r) for r in roles if str(r).strip()],
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "amr": ["oidc"],
            "jti": _urlsafe(18),
        }
        token = jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        return {
            "access_token": token,
            "expires_in": int(exp.timestamp() - now.timestamp()),
            "user_id": user_id,
            "org_id": org_id,
        }


iam_oidc_service = IamOidcService()
