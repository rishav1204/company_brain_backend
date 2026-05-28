def validate_dispatch(*, notification_type: str, channel: str) -> None:
    if not notification_type.strip():
        raise ValueError("notification_type required")
    if not channel.strip():
        raise ValueError("channel required")
