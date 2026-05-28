from fastapi import APIRouter

from app.modules.platform.notifications.routes import (
    notification_routes,
    preference_routes,
    realtime_routes,
    template_routes,
    webhook_routes,
)

notifications_router = APIRouter()
notifications_router.include_router(notification_routes.router)
notifications_router.include_router(preference_routes.router)
notifications_router.include_router(template_routes.router)
notifications_router.include_router(realtime_routes.router)
notifications_router.include_router(webhook_routes.router)
