from __future__ import annotations


class ComplianceError(Exception):
    pass


class ObligationNotFoundError(ComplianceError):
    pass


class RuleNotFoundError(ComplianceError):
    pass
