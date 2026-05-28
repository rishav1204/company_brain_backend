from unittest.mock import patch

from app.modules.core.iam.services.identity_resolver import DEV_USER_EMAIL, DEV_USER_UUID, same_actor


@patch("app.modules.core.iam.services.identity_resolver.user_repo.get_by_email")
def test_same_actor_email_vs_uuid(mock_get) -> None:
    mock_get.return_value = {"id": DEV_USER_UUID, "org_id": "11111111-1111-4111-8111-111111111111"}
    assert same_actor(
        "11111111-1111-4111-8111-111111111111",
        DEV_USER_EMAIL,
        DEV_USER_UUID,
    )


def test_same_actor_direct_uuid() -> None:
    assert same_actor("org-1", "user-a", "user-a")
