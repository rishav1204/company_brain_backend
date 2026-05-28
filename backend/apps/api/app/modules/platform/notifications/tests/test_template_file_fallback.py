from app.modules.platform.notifications.services.template_service import template_service


def test_file_fallback_approval_request() -> None:
    subject, body = template_service.render(
        "org-1",
        template_key="approval_request",
        channel="email",
        variables={"recipient_name": "Rishav", "entity_label": "INV-1", "amount": "100"},
    )
    assert "Rishav" in body or "INV-1" in body
    assert subject is not None
