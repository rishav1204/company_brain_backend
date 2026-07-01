import hashlib

from app.modules.core.iam.repositories.mfa_repository import mfa_repo


def device_fingerprint_from_request(*, user_agent: str = "", client_hint: str = "") -> str:
    raw = f"{user_agent}|{client_hint}".strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def trust_device_for_user(
    org_id: str,
    user_id: str,
    fingerprint: str,
    device_info: dict | None = None,
    *,
    trust_days: int = 30,
) -> dict:
    device_name = (device_info or {}).get("device_name") or (device_info or {}).get("user_agent", "")[:120]
    device = mfa_repo.register_device(org_id, user_id, fingerprint, device_name=device_name)
    return mfa_repo.trust_device(org_id, user_id, device["id"], trust_days=trust_days)
