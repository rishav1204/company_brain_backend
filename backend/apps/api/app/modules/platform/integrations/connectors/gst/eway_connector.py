from __future__ import annotations

from app.modules.platform.integrations.connectors.gst.stub_gst_connector import StubGstConnector
from app.modules.platform.integrations.services.connector_registry import connector_registry


class StubEwayConnector(StubGstConnector):
    connector_type = "eway"
    provider_name = "stub_eway"


connector_registry.register(StubEwayConnector())
