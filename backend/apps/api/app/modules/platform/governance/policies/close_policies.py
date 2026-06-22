CLOSE_POLICIES = [
    {
        "policy_code": "FISCAL_PERIOD_LOCK",
        "policy_name": "Fiscal Period Close Lock",
        "policy_type": "fiscal",
        "conditions": {"closed_period": True, "action": "journal.post"},
        "actions": {"block": True},
    },
    {
        "policy_code": "PERIOD_CLOSE_APPROVAL",
        "policy_name": "Period Close Requires CFO",
        "policy_type": "approval",
        "conditions": {"action": "period.close"},
        "actions": {"require_role": "cfo"},
    },
]
