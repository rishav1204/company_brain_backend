import pytest

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker


def test_maker_checker_blocks_self_approval() -> None:
    with pytest.raises(MakerCheckerViolation):
        enforce_maker_checker(created_by="user-1", actor_user_id="user-1")


def test_maker_checker_allows_different_actors() -> None:
    enforce_maker_checker(created_by="user-1", actor_user_id="user-2")
