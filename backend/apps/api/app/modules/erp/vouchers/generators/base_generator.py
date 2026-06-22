from __future__ import annotations

from abc import ABC, abstractmethod


class BaseVoucherGenerator(ABC):
    @abstractmethod
    def generate_lines(self, org_id: str, *, payload: dict) -> list[dict]:
        raise NotImplementedError

    def validate_business_rules(self, org_id: str, *, payload: dict) -> None:
        return None
