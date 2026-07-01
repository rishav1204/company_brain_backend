"""Thin compatibility shim — delegates to IAM OIDC service."""

from app.modules.core.iam.services.oidc_service import IamOidcService, iam_oidc_service


class OidcService(IamOidcService):
    def issue_api_session(self, claims: dict, **kwargs) -> dict:
        return self.complete_login(
            claims,
            device_info=kwargs.get("device_info"),
            ip_address=kwargs.get("ip_address"),
        )

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

__all__ = ["oidc_service", "OidcService"]
