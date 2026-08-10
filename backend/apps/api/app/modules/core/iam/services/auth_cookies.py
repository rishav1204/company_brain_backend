"""HttpOnly access-token cookie for browser SSE (EventSource cannot send Authorization)."""

from __future__ import annotations

from fastapi import Response

from app.core.config import settings

ACCESS_TOKEN_COOKIE = "cb_access_token"


def _cookie_secure() -> bool:
    return settings.app_env.lower() == "prod" or settings.auth_cookie_secure


def set_access_token_cookie(response: Response, access_token: str, *, max_age: int) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=max_age,
        httponly=True,
        secure=_cookie_secure(),
        samesite="strict" if settings.app_env.lower() == "prod" else "lax",
        path="/",
    )


def clear_access_token_cookie(response: Response) -> None:
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        path="/",
        secure=_cookie_secure(),
        samesite="strict" if settings.app_env.lower() == "prod" else "lax",
    )
