from __future__ import annotations


class PeriodClosedError(Exception):
    def __init__(self, *, code: str, message: str, period_name: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.period_name = period_name

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "period_name": self.period_name}
