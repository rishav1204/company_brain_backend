from fastapi import APIRouter

from app.modules.platform.governance.routes import (
    audit_routes,
    compliance_routes,
    evidence_routes,
    forensics_routes,
    governance_routes,
    policy_routes,
    policy_engine_routes,
)

governance_router = APIRouter()
governance_router.include_router(audit_routes.router)
governance_router.include_router(compliance_routes.router)
governance_router.include_router(governance_routes.router)
governance_router.include_router(policy_routes.router)
governance_router.include_router(policy_engine_routes.router)
governance_router.include_router(evidence_routes.router)
governance_router.include_router(forensics_routes.router)
