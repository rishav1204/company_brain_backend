import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from time import sleep

import httpx

from app.core.config import settings
from app.services.logger import log_event


@dataclass
class IntegrationResult:
    status: str
    target: str
    detail: str
    response_code: int | None = None


class IntegrationService:
    def _retry_delays(self) -> list[float]:
        return [0.0] + [0.3 * (2**i) for i in range(max(0, settings.integration_max_retries - 1))]

    def _post_json(self, url: str, payload: dict, target: str) -> IntegrationResult:
        if not url:
            return IntegrationResult(status="error", target=target, detail="target_not_configured")
        last_error = "unknown_error"
        for delay in self._retry_delays():
            if delay > 0:
                sleep(delay)
            try:
                response = httpx.post(url, json=payload, timeout=settings.integration_timeout_seconds)
                if 200 <= response.status_code < 300:
                    return IntegrationResult(
                        status="completed",
                        target=target,
                        detail="request_delivered",
                        response_code=response.status_code,
                    )
                last_error = f"http_{response.status_code}"
            except Exception as exc:
                last_error = str(exc)
        log_event("integration.failed", target=target, detail=last_error)
        return IntegrationResult(status="error", target=target, detail=last_error)

    def send_slack(self, channel: str, text: str) -> IntegrationResult:
        payload = {"channel": channel, "text": text}
        return self._post_json(settings.slack_webhook_url, payload, target="slack")

    def send_email(self, to: str, subject: str, body: str) -> IntegrationResult:
        if not (settings.smtp_host and settings.smtp_from_email):
            return IntegrationResult(status="error", target="email", detail="smtp_not_configured")
        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.integration_timeout_seconds) as server:
                server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(message)
            return IntegrationResult(status="completed", target="email", detail="sent")
        except Exception as exc:
            log_event("integration.failed", target="email", detail=str(exc))
            return IntegrationResult(status="error", target="email", detail=str(exc))

    def create_jira_issue(self, summary: str, description: str) -> IntegrationResult:
        if not (settings.jira_base_url and settings.jira_email and settings.jira_api_token and settings.jira_project_key):
            return IntegrationResult(status="error", target="jira", detail="jira_not_configured")
        url = settings.jira_base_url.rstrip("/") + "/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": settings.jira_project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Task"},
            }
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                auth=(settings.jira_email, settings.jira_api_token),
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return IntegrationResult(status="completed", target="jira", detail="issue_created", response_code=response.status_code)
            return IntegrationResult(status="error", target="jira", detail=f"http_{response.status_code}", response_code=response.status_code)
        except Exception as exc:
            return IntegrationResult(status="error", target="jira", detail=str(exc))

    def create_linear_issue(self, title: str, description: str) -> IntegrationResult:
        if not (settings.linear_api_key and settings.linear_team_id):
            return IntegrationResult(status="error", target="linear", detail="linear_not_configured")
        url = "https://api.linear.app/graphql"
        payload = {
            "query": """
                mutation IssueCreate($input: IssueCreateInput!) {
                  issueCreate(input: $input) { success }
                }
            """,
            "variables": {
                "input": {
                    "teamId": settings.linear_team_id,
                    "title": title,
                    "description": description,
                }
            },
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"Authorization": settings.linear_api_key, "Content-Type": "application/json"},
                timeout=settings.integration_timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return IntegrationResult(status="completed", target="linear", detail="issue_created", response_code=response.status_code)
            return IntegrationResult(status="error", target="linear", detail=f"http_{response.status_code}", response_code=response.status_code)
        except Exception as exc:
            return IntegrationResult(status="error", target="linear", detail=str(exc))

    def push_erp(self, payload: dict) -> IntegrationResult:
        return self._post_json(settings.erp_webhook_url, payload, target="erp")

    def push_bank(self, payload: dict) -> IntegrationResult:
        return self._post_json(settings.bank_webhook_url, payload, target="bank")

    def push_crm(self, payload: dict) -> IntegrationResult:
        return self._post_json(settings.crm_webhook_url, payload, target="crm")

    def push_docs(self, payload: dict) -> IntegrationResult:
        return self._post_json(settings.docs_webhook_url, payload, target="docs")

    def push_ticketing(self, payload: dict) -> IntegrationResult:
        return self._post_json(settings.ticketing_webhook_url, payload, target="ticketing")


integration_service = IntegrationService()
