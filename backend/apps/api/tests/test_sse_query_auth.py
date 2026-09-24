"""EventSource cannot send Authorization headers — SSE must accept query tokens."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.api.deps import _authorization_from_request, _is_sse_stream_path
from app.middleware import _is_sse_stream_path as mw_is_sse


def test_sse_path_detection_covers_frontend_urls() -> None:
    assert _is_sse_stream_path("/api/v1/realtime/action-center/sse")
    assert _is_sse_stream_path("/api/v1/workflows/events/stream/sse")
    assert _is_sse_stream_path("/api/v1/workflows/events/stream")
    assert mw_is_sse("/api/v1/realtime/action-center/sse")
    assert mw_is_sse("/api/v1/workflows/events/stream/sse")
    assert not _is_sse_stream_path("/api/v1/auth/password/login")


def test_sse_accepts_access_token_query_param() -> None:
    request = MagicMock()
    request.url.path = "/api/v1/realtime/action-center/sse"
    request.headers.get.return_value = None
    request.cookies.get.return_value = None
    request.query_params.get.side_effect = lambda k: "jwt-from-eventsource" if k == "access_token" else None

    auth = _authorization_from_request(request, authorization=None)
    assert auth == "Bearer jwt-from-eventsource"


def test_non_sse_ignores_access_token_query_param() -> None:
    request = MagicMock()
    request.url.path = "/api/v1/erp/ap/invoices"
    request.headers.get.return_value = None
    request.cookies.get.return_value = None
    request.query_params.get.side_effect = lambda k: "jwt-leak" if k == "access_token" else None

    auth = _authorization_from_request(request, authorization=None)
    assert auth is None
