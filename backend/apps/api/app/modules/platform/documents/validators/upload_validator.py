from app.modules.platform.documents.validators.mime_validator import validate_mime_type


def validate_upload_payload(*, file_name: str, mime_type: str, file_size: int) -> None:
    if not file_name or len(file_name.strip()) < 1:
        raise ValueError("file_name is required")
    if file_size < 0:
        raise ValueError("file_size must be >= 0")
    if file_size > 50 * 1024 * 1024:
        raise ValueError("file_size exceeds 50MB limit")
    validate_mime_type(mime_type)
