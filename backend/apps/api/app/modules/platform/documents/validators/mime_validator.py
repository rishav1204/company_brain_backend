ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "text/csv",
    "application/xml",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def validate_mime_type(mime_type: str) -> None:
    normalized = (mime_type or "").strip().lower()
    if normalized not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported mime type: {mime_type}")
