from __future__ import annotations


def analyze_notice(*, notice_type: str, metadata: dict) -> dict:
    ntype = str(notice_type).lower()
    category = "demand" if "demand" in ntype else ("show_cause" if "show" in ntype else "general")
    actions = []
    if category == "demand":
        actions = ["Review tax computation", "Gather supporting invoices", "Consult tax advisor before response"]
    elif category == "show_cause":
        actions = ["Prepare written submission", "Attach GSTR-2B reconciliation", "File response before due date"]
    else:
        actions = ["Acknowledge receipt", "Classify notice type", "Assign to compliance team"]
    return {
        "category": category,
        "summary": f"GST notice classified as {category}. Review required.",
        "suggested_actions": actions,
        "metadata": metadata,
    }
