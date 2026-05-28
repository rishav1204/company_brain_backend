from dataclasses import dataclass


@dataclass
class PreferenceRecord:
    channel: str
    notification_type: str
    enabled: bool
    quiet_hours: dict
