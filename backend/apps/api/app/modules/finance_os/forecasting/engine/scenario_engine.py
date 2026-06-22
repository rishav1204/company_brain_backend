from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    name: str
    collections_multiplier: float = 1.0
    expenses_multiplier: float = 1.0


DEFAULT_SCENARIOS = [
    Scenario(name="expected", collections_multiplier=1.0, expenses_multiplier=1.0),
    Scenario(name="optimistic", collections_multiplier=1.2, expenses_multiplier=0.95),
    Scenario(name="conservative", collections_multiplier=0.8, expenses_multiplier=1.05),
]

