from datetime import datetime, timezone


class DevAuthStore:
    def __init__(self) -> None:
        self.users_by_email: dict[str, dict] = {}

    def create_user(self, email: str, password: str, org_id: str, roles: list[str], display_name: str | None = None) -> dict:
        user = {
            "user_id": f"dev-user-{email.lower()}",
            "email": email.lower(),
            "password": password,
            "org_id": org_id,
            "roles": roles,
            "display_name": display_name or email.split("@")[0],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.users_by_email[user["email"]] = user
        return user

    def get_user(self, email: str) -> dict | None:
        return self.users_by_email.get(email.lower())


dev_auth_store = DevAuthStore()
