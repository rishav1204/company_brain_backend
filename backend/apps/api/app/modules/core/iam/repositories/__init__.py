from app.modules.core.iam.repositories.organization_repository import OrganizationRepository
from app.modules.core.iam.repositories.permission_repository import PermissionRepository
from app.modules.core.iam.repositories.role_repository import RoleRepository
from app.modules.core.iam.repositories.session_repository import SessionRepository
from app.modules.core.iam.repositories.user_repository import UserRepository

organization_repo = OrganizationRepository()
user_repo = UserRepository()
role_repo = RoleRepository()
permission_repo = PermissionRepository()
session_repo = SessionRepository()

__all__ = [
    "organization_repo",
    "user_repo",
    "role_repo",
    "permission_repo",
    "session_repo",
]
