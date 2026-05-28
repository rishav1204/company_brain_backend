from dataclasses import dataclass


@dataclass
class DocumentModel:
    id: str
    org_id: str
    document_type: str
    file_name: str
    mime_type: str
    storage_path: str
