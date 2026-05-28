from __future__ import annotations

from typing import Protocol


class MessagingAdapter(Protocol):
    def send_message(self, *, target: str, text: str) -> dict: ...

