from fastapi import APIRouter

from app.modules.core.iam.routes import (
    admin_routes,
    api_key_routes,
    auth_routes,
    invite_routes,
    mfa_routes,
    organization_routes,
    permission_routes,
    role_routes,
    session_routes,
    user_routes,
)

router = APIRouter()
router.include_router(admin_routes.router)
router.include_router(auth_routes.router)
router.include_router(user_routes.router)
router.include_router(role_routes.router)
router.include_router(permission_routes.router)
router.include_router(session_routes.router)
router.include_router(organization_routes.router)
router.include_router(mfa_routes.router)
router.include_router(invite_routes.router)
router.include_router(api_key_routes.router)
