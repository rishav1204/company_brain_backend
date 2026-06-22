from __future__ import annotations

from typing import Any

from app.modules.core.iam.repositories import organization_repo


class BranchService:
    def list_for_company(self, org_id: str, company_id: str) -> list[dict[str, Any]]:
        rows = organization_repo.list_branches(org_id, company_id=company_id)
        return [
            {
                "id": row.get("id"),
                "company_id": row.get("company_id"),
                "branch_code": row.get("branch_code"),
                "branch_name": row.get("branch_name"),
                "state_code": row.get("state_code"),
                "gstin": row.get("gstin"),
            }
            for row in rows
        ]

    def list_all(self, org_id: str) -> list[dict[str, Any]]:
        return organization_repo.list_branches(org_id)


branch_service = BranchService()
