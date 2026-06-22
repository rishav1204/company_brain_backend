GST_POLICIES = [
    {
        "policy_code": "GST_FILING_RECON_001",
        "policy_name": "GST Filing Requires Reconciliation",
        "policy_type": "compliance",
        "conditions": {"action": "gst.file"},
        "actions": {"block": True, "require_reconciliation": True},
    },
]
