"""
Connector implementations live under this package.

Importing this package should register all connectors into the registry.
"""

from app.modules.platform.integrations.connectors import ocr  # noqa: F401
from app.modules.platform.integrations.connectors.email import stub_email_connector  # noqa: F401
from app.modules.platform.integrations.connectors.banks import stub_bank_connector  # noqa: F401
from app.modules.platform.integrations.connectors.gst import stub_gst_connector  # noqa: F401

