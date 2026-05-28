from dataclasses import dataclass


@dataclass
class VersionModel:
    id: str
    document_id: str
    version_number: int
    storage_path: str
