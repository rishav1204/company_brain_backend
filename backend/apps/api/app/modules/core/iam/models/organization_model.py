from dataclasses import dataclass


@dataclass
class OrganizationRecord:
    id: str
    name: str
    slug: str
    status: str
    currency: str
