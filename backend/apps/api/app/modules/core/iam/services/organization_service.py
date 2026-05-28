from app.modules.core.iam.repositories import organization_repo


class OrganizationService:
    def get_current(self, org_id: str) -> dict | None:
        return organization_repo.get_organization(org_id)

    def list_companies(self, org_id: str) -> list[dict]:
        return organization_repo.list_companies(org_id)

    def list_branches(self, org_id: str, company_id: str | None = None) -> list[dict]:
        return organization_repo.list_branches(org_id, company_id=company_id)


organization_service = OrganizationService()
