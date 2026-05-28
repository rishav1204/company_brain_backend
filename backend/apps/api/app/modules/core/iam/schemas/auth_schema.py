from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class LoginResponse(BaseModel):
    request_id: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    org_id: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    confidence: float
    verification_status: str


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
