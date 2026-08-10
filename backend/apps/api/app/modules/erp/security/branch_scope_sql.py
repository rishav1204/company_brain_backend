from __future__ import annotations


def branch_ids_from_attrs(attrs: dict | None) -> list[str] | None:
    """Return allowed branch IDs when user is branch-scoped; None means no filter."""
    attrs = attrs or {}
    allowed = attrs.get("allowed_branch_ids")
    if isinstance(allowed, list) and allowed:
        ids = [str(b) for b in allowed if b]
        return ids or None
    return None


def resolve_branch_id_for_write(
    attrs: dict | None,
    *,
    explicit_branch_id: str | None = None,
) -> str | None:
    """Pick branch_id for creates: explicit value (validated) or sole allowed branch."""
    allowed = branch_ids_from_attrs(attrs)
    if explicit_branch_id:
        bid = str(explicit_branch_id)
        if allowed and bid not in allowed:
            raise ValueError("branch_id not in allowed branch scope")
        return bid
    if allowed and len(allowed) == 1:
        return allowed[0]
    return None


def branch_filter_clause(
    attrs: dict | None,
    *,
    column: str = "branch_id",
) -> tuple[str, list]:
    """Append SQL fragment + params when user is branch-scoped via ABAC attrs."""
    attrs = attrs or {}
    allowed = attrs.get("allowed_branch_ids")
    if isinstance(allowed, list) and allowed:
        ids = [str(b) for b in allowed if b]
        if ids:
            return f" AND ({column} IS NULL OR {column}::text = ANY(%s))", [ids]
    return "", []
