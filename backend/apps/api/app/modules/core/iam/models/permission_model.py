from dataclasses import dataclass


@dataclass
class PermissionRecord:
    id: str
    resource: str
    action: str
    permission_key: str
