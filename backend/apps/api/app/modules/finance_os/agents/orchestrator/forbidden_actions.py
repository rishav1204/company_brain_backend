from __future__ import annotations

FORBIDDEN_TOOLS = {"journal", "payment", "gst", "gst_filing", "ledger"}

FORBIDDEN_ERP_METHODS = {"writeback", "postJournal", "executePayment", "fileGst"}

# Read-only agent tools allowed without explicit approval when policy passes.
READ_ONLY_AGENT_TOOLS = {
    ("memory", "search"),
    ("graph", "traverse"),
}

# Side-effecting tools require human approval unless payload carries human_approved=True.
SIDE_EFFECT_AGENT_TOOLS = {
    ("email", "send"),
    ("email", "postmessage"),
    ("slack", "postmessage"),
    ("jira", "createissue"),
    ("linear", "createissue"),
    ("workflow", "transition"),
    ("erp", "writeback"),
}


def normalize_tool_method(tool: str, method: str) -> tuple[str, str]:
    tool_l = str(tool).lower()
    method_l = str(method).lower()
    if tool_l == "email" and method_l == "postmessage":
        method_l = "send"
    if tool_l == "erp" and method_l in {"updatestatus", "writeback"}:
        method_l = "writeback"
    return tool_l, method_l


def is_agent_tool_allowed(tool: str, method: str) -> bool:
    tool_l, method_l = normalize_tool_method(tool, method)
    if is_forbidden_action(tool_l, method_l):
        return False
    pair = (tool_l, method_l)
    if pair in READ_ONLY_AGENT_TOOLS:
        return True
    if pair in SIDE_EFFECT_AGENT_TOOLS:
        return True
    if tool_l == "workflow":
        return True
    return False


def agent_tool_requires_approval(tool: str, method: str) -> bool:
    tool_l, method_l = normalize_tool_method(tool, method)
    pair = (tool_l, method_l)
    if pair in READ_ONLY_AGENT_TOOLS:
        return False
    return True


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
