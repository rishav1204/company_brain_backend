"""
OCR connectors (provider implementations live here).

Importing this module registers connectors in the ConnectorRegistry.
"""

from app.modules.platform.integrations.connectors.ocr import aws_textract_connector, gcp_documentai_connector  # noqa: F401

