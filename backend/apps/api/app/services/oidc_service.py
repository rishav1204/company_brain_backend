"""Thin compatibility shim — delegates to IAM OIDC service with legacy API-session helpers."""

from __future__ import annotations

from app.core.config import settings
from app.modules.core.iam.services.oidc_service import IamOidcService, iam_oidc_service
from app.modules.core.iam.services.auth_service import AuthError, iam_db_enabled


class OidcService(IamOidcService):
    def _prod_jwks_mode(self) -> bool:
        return settings.app_env.lower() == "prod" and settings.jwt_require_jwks_in_prod

    def issue_api_session(self, claims: dict, **kwargs) -> dict:
        """Mint an API session from IdP claims.

        Production with JWT JWKS policy reuses an upstream token that verifies under
        `decode_bearer_token`. Non-prod falls back to local JWT issuance when core IAM
        cannot resolve the IdP subject (dev / unit tests).
        """
        upstream_access_token = kwargs.get("upstream_access_token")
        upstream_id_token = kwargs.get("upstream_id_token")
        include_refresh = kwargs.get("include_refresh", True)

        if self._prod_jwks_mode():
            from app.services.jwt_auth import decode_bearer_token

            runtime_token = ""
            principal = None
            for candidate in (upstream_access_token or "", upstream_id_token or ""):
                if not candidate:
                    continue
                try:
                    principal = decode_bearer_token(candidate)
                    runtime_token = candidate
                    break
                except Exception:
                    continue
            if not runtime_token or principal is None:
                raise ValueError("OIDC upstream token is not compatible with API JWT verification policy")
            return {
                "access_token": runtime_token,
                "expires_in": max(300, settings.api_session_ttl_seconds),
                "org_id": principal.org_id,
                "user_id": principal.user_id,
                "roles": principal.roles,
            }

        if iam_db_enabled():
            try:
                return self.complete_login(
                    claims,
                    device_info=kwargs.get("device_info"),
                    ip_address=kwargs.get("ip_address"),
                )
            except AuthError:
                # Synthetic claims (unit tests) may not match provisioned IdP links.
                if settings.app_env.lower() == "prod":
                    raise
                result = self._legacy_token_session(claims)
                if not include_refresh:
                    result.pop("refresh_token", None)
                return result

        result = self._legacy_token_session(claims)
        if not include_refresh:
            result.pop("refresh_token", None)
        return result

    def refresh_api_session(self, refresh_token: str) -> dict:
        from app.modules.core.iam.services.auth_service import refresh

        return refresh(refresh_token=refresh_token)

    def revoke_access_token(self, access_token: str) -> None:
        from app.modules.core.iam.services.token_revocation import revoke_access_token_jti

        revoke_access_token_jti(access_token)

    def logout(self, refresh_token: str | None = None, access_token: str | None = None) -> None:
        from app.modules.core.iam.services.auth_service import logout
        from app.modules.core.iam.services.session_service import resolve_refresh_session
        from app.services.jwt_auth import decode_bearer_token

        org_id = user_id = session_id = None
        if refresh_token:
            session = resolve_refresh_session(refresh_token)
            if session:
                org_id, user_id, session_id = session["org_id"], session["user_id"], session["id"]
        if access_token and not session_id:
            try:
                principal = decode_bearer_token(access_token)
                org_id, user_id, session_id = principal.org_id, principal.user_id, principal.session_id
            except Exception:
                pass
        if org_id and user_id and session_id:
            logout(org_id=org_id, session_id=session_id, user_id=user_id, access_token=access_token)


oidc_service = OidcService()

__all__ = ["oidc_service", "OidcService", "iam_oidc_service"]
