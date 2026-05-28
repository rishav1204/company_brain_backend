from app.modules.platform.notifications.services.quiet_hours import in_quiet_hours


def test_quiet_hours_in_range() -> None:
    assert in_quiet_hours({"start": "00:00:00", "end": "23:59:59"}) is True


def test_quiet_hours_empty() -> None:
    assert in_quiet_hours({}) is False
