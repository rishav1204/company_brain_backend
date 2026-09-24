from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Password login. Org is optional when the email uniquely identifies a user.

    When the same email exists in multiple orgs, pass ``org_id`` or ``org_slug``.
    """

    email: str
    password: str
    mfa_code: str | None = None
    org_id: str | None = None
    org_slug: str | None = None


class LoginResponse(BaseModel):
    """Full session, or MFA challenge after password OK."""

    request_id: str
    mfa_required: bool = False
    mfa_challenge_token: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int | None = None
    user_id: str | None = None
    org_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    confidence: float = 0.99
    verification_status: str = "iam_db_login"


class MfaVerifyRequest(BaseModel):
    mfa_challenge_token: str
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str
    mfa_code: str | None = None


class RefreshResponse(BaseModel):
    request_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    org_id: str
    confidence: float
    verification_status: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
