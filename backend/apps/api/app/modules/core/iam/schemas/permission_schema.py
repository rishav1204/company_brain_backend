from pydantic import BaseModel


class PermissionResponse(BaseModel):
    id: str
    resource: str
    action: str
    permission_key: str
    description: str | None = None


class PermissionListResponse(BaseModel):
    request_id: str
    items: list[PermissionResponse]
    confidence: float
    verification_status: str
