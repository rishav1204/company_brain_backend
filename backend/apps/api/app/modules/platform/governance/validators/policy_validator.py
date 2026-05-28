from __future__ import annotations


def validate_policy_rule(policy_key: str, policy_type: str, conditions: dict, actions: dict) -> None:
    if not policy_key.strip():
        raise ValueError("policy_key is required")
    if not policy_type.strip():
        raise ValueError("policy_type is required")
    if not isinstance(conditions, dict):
        raise ValueError("conditions must be a dict")
    if not isinstance(actions, dict):
        raise ValueError("actions must be a dict")
