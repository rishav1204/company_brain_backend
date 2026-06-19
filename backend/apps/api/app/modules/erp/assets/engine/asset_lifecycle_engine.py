from __future__ import annotations

CAPITALIZABLE = {"draft"}
DEPRECIABLE = {"active", "impaired"}
TRANSFERABLE = {"active", "impaired"}
DISPOSABLE = {"active", "impaired", "fully_depreciated"}
IMPAIRABLE = {"active"}


def ensure_capitalizable(status: str) -> None:
    if status not in CAPITALIZABLE:
        raise ValueError(f"Asset cannot be capitalized from status {status}")


def ensure_depreciable(status: str) -> None:
    if status not in DEPRECIABLE:
        raise ValueError(f"Asset cannot be depreciated from status {status}")


def ensure_transferable(status: str) -> None:
    if status not in TRANSFERABLE:
        raise ValueError(f"Asset cannot be transferred from status {status}")


def ensure_disposable(status: str) -> None:
    if status not in DISPOSABLE:
        raise ValueError(f"Asset cannot be disposed from status {status}")


def ensure_impairable(status: str) -> None:
    if status not in IMPAIRABLE:
        raise ValueError(f"Asset cannot be impaired from status {status}")


def next_status_after_depreciation(*, book_value: float, salvage_value: float) -> str | None:
    if book_value <= salvage_value:
        return "fully_depreciated"
    return None
