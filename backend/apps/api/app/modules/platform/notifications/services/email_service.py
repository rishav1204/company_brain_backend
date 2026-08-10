"""Thin email facade for IAM and security-sensitive sends (SEC-14)."""

from __future__ import annotations

from app.modules.platform.notifications.providers.email_provider import email_provider


class EmailDeliveryError(Exception):
    pass


class EmailService:
    def send_email(self, *, to: str, subject: str, body: str) -> None:
        result = email_provider.send(to=to, subject=subject, body=body)
        if result.status != "completed":
            raise EmailDeliveryError(result.detail or f"Email delivery failed via {result.provider}")


email_service = EmailService()
