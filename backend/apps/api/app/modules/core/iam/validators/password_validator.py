import re

_MIN_LENGTH = 12
_SPECIAL = re.compile(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]")


def validate_password_strength(password: str) -> None:
    if len(password) < _MIN_LENGTH:
        raise ValueError(f"Password must be at least {_MIN_LENGTH} characters")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must include an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must include a lowercase letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("Password must include a digit")
    if not _SPECIAL.search(password):
        raise ValueError("Password must include a special character")
