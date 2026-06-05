from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.journals.repositories.recurring_repository import recurring_repository
from app.modules.erp.journals.services.approval_service import approval_service
from app.modules.erp.journals.services.journal_service import journal_service


def _advance_date(d: date, frequency: str) -> date:
    freq = frequency.lower()
    if freq == "daily":
        return d + timedelta(days=1)
    if freq == "weekly":
        return d + timedelta(weeks=1)
    if freq == "monthly":
        month = d.month + 1
        year = d.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return date(year, month, min(d.day, 28))
    if freq == "quarterly":
        month = d.month + 3
        year = d.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return date(year, month, min(d.day, 28))
    if freq == "yearly":
        return date(d.year + 1, d.month, d.day)
    raise ValueError(f"Invalid frequency: {frequency}")


class RecurringJournalService:
    def create_template(
        self,
        org_id: str,
        *,
        template_name: str,
        frequency: str,
        next_run_date: str,
        journal_template: dict,
        company_id: str | None = None,
    ) -> dict:
        if frequency not in {"daily", "weekly", "monthly", "quarterly", "yearly"}:
            raise ValueError("Invalid frequency")
        return recurring_repository.create(
            org_id,
            template_name=template_name,
            frequency=frequency,
            next_run_date=next_run_date,
            journal_template=journal_template,
            company_id=company_id,
        )

    def list_templates(self, org_id: str, *, active_only: bool = True) -> list[dict]:
        return recurring_repository.list(org_id, active_only=active_only)

    def deactivate(self, org_id: str, *, recurring_id: str) -> dict:
        return recurring_repository.deactivate(org_id, recurring_id=recurring_id)

    def run_due(self, org_id: str, *, as_of_date: str | None = None) -> list[dict]:
        run_date = as_of_date or date.today().isoformat()
        due = recurring_repository.list_due(org_id, as_of_date=run_date)
        created: list[dict] = []
        for template in due:
            tpl = template.get("journal_template") if isinstance(template.get("journal_template"), dict) else {}
            journal = journal_service.create_draft(
                org_id,
                created_by=None,
                journal_type=str(tpl.get("journal_type") or "general"),
                posting_date=run_date,
                description=str(tpl.get("description") or template.get("template_name")),
                source_type="recurring_journal",
                source_id=str(template.get("id")),
                company_id=tpl.get("company_id"),
                lines=tpl.get("lines") or [],
                idempotency_key=f"recurring:{template['id']}:{run_date}",
            )
            journal_id = str(journal["journal"]["id"])

            # Blueprint: draft → approval workflow → posting
            try:
                approval_service.submit_for_approval(org_id, journal_id=journal_id, actor_id=None)
            except Exception:
                # If already submitted/approved or fails validation, keep as draft for manual fix.
                pass
            try:
                from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

                handle_entity_created(
                    org_id=org_id,
                    payload={
                        "entity_type": "journal",
                        "entity_id": journal_id,
                        "event": "scheduler.tick",
                        "metadata": {
                            "journal_id": journal_id,
                            "source": "recurring_journal",
                            "recurring_id": str(template.get("id") or ""),
                            "run_date": run_date,
                        },
                    },
                )
            except Exception:
                pass

            next_date = _advance_date(date.fromisoformat(run_date), str(template.get("frequency")))
            recurring_repository.advance_next_run(org_id, recurring_id=str(template["id"]), next_run_date=next_date.isoformat())
            created.append({"recurring_id": template["id"], "journal_id": journal_id})
        return created


recurring_journal_service = RecurringJournalService()
