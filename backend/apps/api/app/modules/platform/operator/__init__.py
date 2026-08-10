"""Cross-tenant platform operator control plane (SaaS owner console).

Every other module answers questions inside a single org, because a JWT carries
one org_id. This module is the deliberate exception: it reads and mutates IAM
state across all orgs, gated by the platform.admin permission.
"""
