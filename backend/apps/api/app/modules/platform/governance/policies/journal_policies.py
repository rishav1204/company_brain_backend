JOURNAL_POLICIES = [
    {
        "policy_code": "JOURNAL_MANUAL_001",
        "policy_name": "Manual Journal Controller Approval",
        "policy_type": "approval",
        "conditions": {"action": "journal.post", "amount_gt": 500000},
        "actions": {"require_role": "controller"},
    },
]
