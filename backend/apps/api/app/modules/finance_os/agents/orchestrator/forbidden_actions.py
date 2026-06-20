from __future__ import annotations

FORBIDDEN_TOOLS = {"journal", "payment", "gst", "gst_filing", "ledger"}

FORBIDDEN_ERP_METHODS = {"writeback", "postJournal", "executePayment", "fileGst"}


def is_forbidden_action(tool: str, method: str) -> bool:
    tool_l = str(tool).lower()
    method_l = str(method).lower()
    if tool_l in FORBIDDEN_TOOLS:
        return True
    if tool_l == "erp" and method_l in FORBIDDEN_ERP_METHODS:
        return True
    if "post" in method_l and tool_l in {"journal", "ledger", "erp"}:
        return True
    if "payment" in method_l and "execute" in method_l:
        return True
    if "file" in method_l and "gst" in method_l:
        return True
    return False


def filter_actions(actions: list) -> tuple[list, list[str]]:
    allowed = []
    blocked: list[str] = []
    for action in actions:
        tool = action.tool if hasattr(action, "tool") else action.get("tool", "")
        method = action.method if hasattr(action, "method") else action.get("method", "")
        if is_forbidden_action(str(tool), str(method)):
            blocked.append(f"{tool}.{method}")
        else:
            allowed.append(action)
    return allowed, blocked
