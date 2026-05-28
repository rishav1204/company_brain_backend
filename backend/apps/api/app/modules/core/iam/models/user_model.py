from dataclasses import dataclass


@dataclass
class UserRecord:
    id: str
    org_id: str
    email: str
    display_name: str
    status: str
    mfa_enabled: bool = False
