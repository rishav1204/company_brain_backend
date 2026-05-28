from dataclasses import dataclass


@dataclass
class RoleRecord:
    id: str
    org_id: str
    name: str
    system_role: bool = False
