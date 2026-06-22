TREASURY_POLICIES = [
    {
        "policy_code": "TREASURY_TRANSFER_001",
        "policy_name": "Inter-bank Transfer Approval",
        "policy_type": "threshold",
        "conditions": {"action": "treasury.transfer", "amount_gt": 5000000},
        "actions": {"require_role": "cfo"},
    },
    {
        "policy_code": "TREASURY_TAX_PAYMENT_001",
        "policy_name": "Tax Payment CFO Approval",
        "policy_type": "approval",
        "conditions": {"action": "payment.execute", "enforce": True},
        "actions": {"require_approval_matrix": True},
    },
]
