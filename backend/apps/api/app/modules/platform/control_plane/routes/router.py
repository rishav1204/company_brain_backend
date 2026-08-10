from fastapi import APIRouter

from app.modules.platform.control_plane.routes.control_plane_routes import router as control_plane_routes

control_plane_router = APIRouter()
control_plane_router.include_router(control_plane_routes)
