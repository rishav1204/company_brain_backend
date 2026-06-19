MAKER_CHECKER_ACTIONS = frozenset(
    {
        "approve",
        "approve_payment",
        "post_journal",
        "release_filing",
        "payment.approve",
        "journal.post",
        "gst.file",
        "tax.modify",
        "tds.file",
        "invoice.approve",
        "bank.reconcile",
        "execute",
        "payment.execute",
    }
)


class MakerCheckerViolation(Exception):
    """Raised when creator attempts to approve their own transaction."""


def requires_maker_checker(action: str) -> bool:
    normalized = action.strip().lower()
    if normalized in MAKER_CHECKER_ACTIONS:
        return True
    return any(normalized.endswith(suffix) for suffix in (".approve", ".post", ".execute", ".file", ".reconcile"))


def enforce_maker_checker(*, created_by: str | None, actor_user_id: str | None, org_id: str | None = None) -> None:
    creator = str(created_by or "").strip()
    actor = str(actor_user_id or "").strip()
    if not creator or not actor:
        return
    if org_id:
        from app.modules.core.iam.services.identity_resolver import same_actor

        if same_actor(org_id, creator, actor):
            raise MakerCheckerViolation("Maker-checker violation: creator cannot approve own transaction")
        return
    if creator == actor:
        raise MakerCheckerViolation("Maker-checker violation: creator cannot approve own transaction")
