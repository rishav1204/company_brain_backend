from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.repositories import organization_repo
from app.modules.core.iam.schemas.organization_schema import (
    BranchResponse,
    CompanyResponse,
    OrganizationResponse,
)

router = APIRouter(tags=["iam-organizations"])


@router.get("/organizations/current", response_model=OrganizationResponse)
def get_current_organization(context=Depends(build_request_context)) -> OrganizationResponse:
    row = organization_repo.get_organization(context.org_id)
    if not row:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse(
        id=row["id"],
        name=row["name"],
        slug=row["slug"],
        status=row["status"],
        country_code=row["country_code"],
        timezone=row["timezone"],
        currency=row["currency"],
        plan=row["plan"],
    )


@router.get("/organizations/companies")
def list_companies(context=Depends(build_request_context)) -> dict:
    rows = organization_repo.list_companies(context.org_id)
    items = [
        CompanyResponse(
            id=row["id"],
            org_id=row["org_id"],
            legal_name=row["legal_name"],
            gstin=row.get("gstin"),
            pan=row.get("pan"),
            base_currency=row["base_currency"],
            financial_year_start=str(row["financial_year_start"]),
        )
        for row in rows
    ]
    return {
        "request_id": context.request_id,
        "items": items,
        "confidence": 0.99,
        "verification_status": "iam_companies_listed",
    }


@router.get("/organizations/branches")
def list_branches(company_id: str | None = None, context=Depends(build_request_context)) -> dict:
    rows = organization_repo.list_branches(context.org_id, company_id=company_id)
    items = [
        BranchResponse(
            id=row["id"],
            company_id=row["company_id"],
            org_id=row["org_id"],
            branch_code=row["branch_code"],
            branch_name=row["branch_name"],
            state_code=row.get("state_code"),
            address=row.get("address") or {},
        )
        for row in rows
    ]
    return {
        "request_id": context.request_id,
        "items": items,
        "confidence": 0.99,
        "verification_status": "iam_branches_listed",
    }
