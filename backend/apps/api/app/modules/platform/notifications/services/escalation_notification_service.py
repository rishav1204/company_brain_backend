from app.modules.platform.notifications.services.notification_service import notification_service


def notify_escalation(org_id: str, *, workflow_id: str, reason: str, recipient_user_id: str | None) -> None:
    notification_service.dispatch(
        org_id,
        notification_type="workflow_escalation",
        channel="in_app",
        priority="high",
        variables={"workflow_id": workflow_id, "reason": reason},
        recipient_user_id=recipient_user_id,
        related_entity_type="workflow_instance",
        related_entity_id=workflow_id,
    )
    notification_service.dispatch(
        org_id,
        notification_type="workflow_escalation",
        channel="email",
        priority="high",
        variables={"workflow_id": workflow_id, "reason": reason},
        recipient_user_id=recipient_user_id,
    )
