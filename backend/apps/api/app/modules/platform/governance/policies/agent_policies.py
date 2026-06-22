AGENT_POLICIES = [
    {
        "policy_code": "AGENT_EXECUTION_DENY",
        "policy_name": "Agent Execution Restrictions",
        "policy_type": "risk",
        "conditions": {"actor_type": "agent"},
        "actions": {"block_execute": True},
    },
]
