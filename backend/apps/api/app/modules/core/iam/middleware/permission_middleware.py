"""Permission enforcement via FastAPI dependencies."""

from app.api.deps import build_request_context, require_api_scope
from app.modules.core.iam.middleware.permission_guard import require_permission

__all__ = ["build_request_context", "require_permission", "require_api_scope"]
