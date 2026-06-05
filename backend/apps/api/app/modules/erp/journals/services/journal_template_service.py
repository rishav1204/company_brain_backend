from __future__ import annotations


class JournalTemplateService:
    def validate_template(self, journal_template: dict) -> None:
        if not isinstance(journal_template, dict):
            raise ValueError("journal_template must be an object")
        lines = journal_template.get("lines")
        if lines is not None and not isinstance(lines, list):
            raise ValueError("journal_template.lines must be a list")

    def build_from_template(self, template: dict, *, posting_date: str) -> dict:
        self.validate_template(template)
        return {
            "journal_type": str(template.get("journal_type") or "general"),
            "description": str(template.get("description") or ""),
            "company_id": template.get("company_id"),
            "lines": template.get("lines") or [],
            "posting_date": posting_date,
        }


journal_template_service = JournalTemplateService()
