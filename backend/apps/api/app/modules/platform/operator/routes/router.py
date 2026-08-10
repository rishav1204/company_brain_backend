from fastapi import APIRouter

from app.modules.platform.operator.routes.operator_routes import router as operator_routes

operator_router = APIRouter()
operator_router.include_router(operator_routes)
