BANKING_POLICIES = [
    {
        "policy_code": "PAYMENT_THRESHOLD_001",
        "policy_name": "Vendor Payment Threshold",
        "policy_type": "threshold",
        "conditions": {"action": "payment.execute"},
        "actions": {"require_approval_matrix": True},
    },
]
