import re

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_org_slug(slug: str) -> None:
    normalized = slug.strip().lower()
    if not normalized or not _SLUG_RE.match(normalized):
        raise ValueError("Organization slug must be lowercase alphanumeric with hyphens")
