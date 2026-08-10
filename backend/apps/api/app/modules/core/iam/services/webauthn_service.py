"""WebAuthn / passkey enrollment and authentication (SEC-01)."""

from __future__ import annotations

import json
import secrets
from typing import Any

from app.core.config import settings
from app.modules.core.iam.repositories.mfa_repository import mfa_repo
from app.services.redis_client import get_redis_client

_CHALLENGE_PREFIX = "iam:webauthn"
_CHALLENGE_TTL = 300


class WebAuthnNotEnabled(Exception):
    pass


def _require_enabled() -> None:
    if not settings.webauthn_enabled:
        raise WebAuthnNotEnabled("WebAuthn is not enabled on this deployment")


def _redis():
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis required for WebAuthn challenges")
    return client


def _store_challenge(kind: str, user_id: str, challenge: bytes) -> None:
    import base64

    _redis().setex(
        f"{_CHALLENGE_PREFIX}:{kind}:{user_id}",
        _CHALLENGE_TTL,
        base64.urlsafe_b64encode(challenge).decode(),
    )


def _pop_challenge(kind: str, user_id: str) -> bytes | None:
    import base64

    key = f"{_CHALLENGE_PREFIX}:{kind}:{user_id}"
    stored = _redis().get(key)
    if not stored:
        return None
    _redis().delete(key)
    return base64.urlsafe_b64decode(str(stored).encode())


def begin_registration(org_id: str, user_id: str, email: str) -> dict:
    _require_enabled()
    from webauthn import generate_registration_options
    from webauthn.helpers import bytes_to_base64url
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        UserVerificationRequirement,
    )

    challenge = secrets.token_bytes(32)
    _store_challenge("reg", user_id, challenge)
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id.encode(),
        user_name=email,
        user_display_name=email,
        challenge=challenge,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        exclude_credentials=[],
    )
    return json.loads(options.model_dump_json())


def finish_registration(org_id: str, user_id: str, credential: dict) -> None:
    _require_enabled()
    from webauthn import verify_registration_response
    from webauthn.helpers.structs import RegistrationCredential

    expected = _pop_challenge("reg", user_id)
    if not expected:
        raise ValueError("Registration challenge expired")

    verification = verify_registration_response(
        credential=RegistrationCredential.parse_raw(json.dumps(credential)),
        expected_challenge=expected,
        expected_rp_id=settings.webauthn_rp_id,
        expected_origin=settings.webauthn_origin,
        require_user_verification=False,
    )
    cred_id = verification.credential_id.decode() if isinstance(verification.credential_id, bytes) else str(verification.credential_id)
    import base64

    stored = {
        "credential_id": cred_id,
        "credential_public_key": base64.b64encode(verification.credential_public_key).decode(),
        "sign_count": verification.sign_count,
        "credential_device_type": str(verification.credential_device_type),
        "credential_backed_up": verification.credential_backed_up,
    }
    mfa_repo.upsert_method(
        org_id,
        user_id,
        "webauthn",
        enabled=True,
        metadata={"credentials": [stored], "credential_id": cred_id},
    )


def begin_authentication(org_id: str, user_id: str) -> dict:
    _require_enabled()
    from webauthn import generate_authentication_options
    from webauthn.helpers.structs import PublicKeyCredentialDescriptor

    method = mfa_repo.get_method(org_id, user_id, "webauthn")
    if not method or not method.get("enabled"):
        raise ValueError("WebAuthn not enrolled")
    meta = method.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    cred_id = meta.get("credential_id")
    if not cred_id:
        raise ValueError("No WebAuthn credential enrolled")

    challenge = secrets.token_bytes(32)
    _store_challenge("auth", user_id, challenge)
    allow = [PublicKeyCredentialDescriptor(id=cred_id.encode() if isinstance(cred_id, str) else cred_id)]
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=challenge,
        allow_credentials=allow,
    )
    return json.loads(options.model_dump_json())


def finish_authentication(org_id: str, user_id: str, assertion: dict) -> bool:
    _require_enabled()
    import base64

    from webauthn import verify_authentication_response
    from webauthn.helpers.structs import AuthenticationCredential

    expected = _pop_challenge("auth", user_id)
    if not expected:
        return False
    method = mfa_repo.get_method(org_id, user_id, "webauthn")
    if not method or not method.get("enabled"):
        return False
    meta = method.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    creds = meta.get("credentials") or []
    if not creds:
        return False
    stored = creds[0]
    try:
        verification = verify_authentication_response(
            credential=AuthenticationCredential.parse_raw(json.dumps(assertion)),
            expected_challenge=expected,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=base64.b64decode(stored["credential_public_key"]),
            credential_current_sign_count=int(stored.get("sign_count") or 0),
            require_user_verification=False,
        )
    except Exception:
        return False
    stored["sign_count"] = verification.new_sign_count
    mfa_repo.upsert_method(
        org_id,
        user_id,
        "webauthn",
        enabled=True,
        metadata={"credentials": [stored], "credential_id": stored.get("credential_id")},
    )
    return True
