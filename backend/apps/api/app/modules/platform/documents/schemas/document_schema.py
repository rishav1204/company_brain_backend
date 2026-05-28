from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentCreateRequest(BaseModel):
    document_type: str = Field(min_length=2, max_length=64)
    file_name: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=3, max_length=128)
    file_size: int = Field(ge=0)
    base64_content: str | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentVersionRequest(BaseModel):
    change_reason: str = Field(default="reupload", max_length=1000)
    file_name: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=3, max_length=128)
    file_size: int = Field(ge=0)
    base64_content: str | None = None
    metadata: dict = Field(default_factory=dict)


class DocumentOut(BaseModel):
    id: str
    document_type: str
    file_name: str
    mime_type: str
    storage_path: str
    checksum_hash: str
    status: str
    file_size: int
    created_at: str | None = None


class CloudinaryDirectUploadSignRequest(BaseModel):
    document_type: str = Field(min_length=2, max_length=64)
    file_name: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=3, max_length=128)


class CloudinaryFinalizeRequest(BaseModel):
    document_type: str = Field(min_length=2, max_length=64)
    file_name: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=3, max_length=128)
    file_size: int = Field(ge=0)
    checksum_hash: str = Field(min_length=16, max_length=128)
    resource_type: str = Field(default="raw", max_length=16)
    public_id: str = Field(min_length=2, max_length=512)
    secure_url: str | None = None
    metadata: dict = Field(default_factory=dict)
