AP_POLICIES = [
    {
        "policy_code": "AP_INVOICE_APPROVAL_001",
        "policy_name": "AP Invoice Approval Threshold",
        "policy_type": "approval",
        "conditions": {"action": "invoice.approve", "amount_gt": 50000},
        "actions": {"require_role": "controller"},
    },
]
