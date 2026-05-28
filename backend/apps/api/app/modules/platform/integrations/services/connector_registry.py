from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CanonicalInvoice:
    invoice_number: str
    vendor_name: str | None = None
    total_amount: float | None = None
    currency: str | None = None
    raw: dict | None = None


class Connector(Protocol):
    connector_type: str
    provider_name: str

    def health(self) -> dict: ...


class OcrConnector(Protocol):
    connector_type: str  # "ocr"
    provider_name: str

    def health(self) -> dict: ...

    def extract_text(self, *, storage_path: str, mime_type: str) -> dict[str, Any]: ...


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[tuple[str, str], Connector] = {}

    def register(self, connector: Connector) -> None:
        key = (connector.connector_type, connector.provider_name)
        self._connectors[key] = connector

    def resolve(self, *, connector_type: str, provider_name: str) -> Connector | None:
        return self._connectors.get((connector_type, provider_name))

    def resolve_ocr(self, *, provider_name: str) -> OcrConnector | None:
        c = self._connectors.get(("ocr", provider_name))
        return c  # type: ignore[return-value]

    def list(self) -> list[dict]:
        return [
            {"connector_type": ct, "provider_name": pn, "health": c.health()}
            for (ct, pn), c in sorted(self._connectors.items(), key=lambda x: (x[0][0], x[0][1]))
        ]


connector_registry = ConnectorRegistry()

