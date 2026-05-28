import re

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


def validate_permission_key(permission_key: str) -> None:
    if not _KEY_RE.match(permission_key.strip().lower()):
        raise ValueError("Permission key must be resource.action (lowercase)")
