from __future__ import annotations

from app.modules.finance_os.audit_explorer.engine.ai_reasoning_engine import explain_execution


def get_ai_decision(org_id: str, execution_id: str) -> dict:
    return explain_execution(org_id, execution_id)
