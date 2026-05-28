from app.modules.platform.notifications.repositories.preference_repository import preference_repository


class PreferenceService:
    def list(self, org_id: str, user_id: str) -> list:
        return preference_repository.list_for_user(org_id, user_id)

    def upsert(self, org_id: str, **kwargs) -> dict:
        return preference_repository.upsert(org_id, **kwargs)


preference_service = PreferenceService()
