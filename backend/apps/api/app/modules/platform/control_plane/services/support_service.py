from __future__ import annotations

from typing import Any

from app.modules.platform.control_plane.repositories.control_plane_repository import (
    control_plane_repository,
)


class SupportService:
    def create_ticket(
        self,
        org_id: str,
        *,
        user_id: str,
        subject: str,
        body: str,
        category: str = "other",
        priority: str = "normal",
    ) -> dict[str, Any]:
        ticket = control_plane_repository.create_ticket(
            org_id,
            user_id=user_id,
            subject=subject,
            category=category,
            priority=priority,
            body=body,
        )
        self._notify_support_event(
            org_id,
            recipient_user_id=user_id,
            notification_type="support.ticket_created",
            ticket_id=str(ticket.get("id") or ""),
            summary=subject,
        )
        return ticket

    def list_for_org(self, org_id: str, **kwargs) -> list[dict[str, Any]]:
        return control_plane_repository.list_tickets(org_id=org_id, **kwargs)

    def list_all(self, **kwargs) -> list[dict[str, Any]]:
        return control_plane_repository.list_tickets(**kwargs)

    def get_thread(self, ticket_id: str) -> dict[str, Any] | None:
        ticket = control_plane_repository.get_ticket(ticket_id)
        if not ticket:
            return None
        messages = control_plane_repository.list_messages(ticket_id)
        return {"ticket": ticket, "messages": messages}

    def reply(
        self,
        ticket_id: str,
        *,
        org_id: str,
        user_id: str,
        body: str,
        author_side: str,
    ) -> dict[str, Any]:
        msg = control_plane_repository.add_message(
            ticket_id=ticket_id,
            org_id=org_id,
            author_user_id=user_id,
            author_side=author_side,
            body=body,
        )
        ticket = control_plane_repository.get_ticket(ticket_id) or {}
        # Notify the opposite side when possible (customer on platform reply).
        recipient = ticket.get("created_by_user_id") if author_side == "platform" else None
        if recipient:
            self._notify_support_event(
                org_id,
                recipient_user_id=str(recipient),
                notification_type="support.message",
                ticket_id=ticket_id,
                summary=(body or "")[:200],
            )
        return msg

    def _notify_support_event(
        self,
        org_id: str,
        *,
        recipient_user_id: str,
        notification_type: str,
        ticket_id: str,
        summary: str,
    ) -> None:
        try:
            from app.modules.platform.notifications.services.notification_service import (
                notification_service,
            )

            notification_service.dispatch(
                org_id,
                notification_type=notification_type,
                channel="in_app",
                priority="medium",
                recipient_user_id=recipient_user_id,
                related_entity_type="support.ticket",
                related_entity_id=ticket_id,
                event_type=notification_type,
                variables={"summary": summary, "ticket_id": ticket_id},
                metadata={"ticket_id": ticket_id},
            )
        except Exception:
            pass


support_service = SupportService()
