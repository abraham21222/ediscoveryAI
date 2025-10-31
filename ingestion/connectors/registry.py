"""Connector registry mapping config types to implementations."""

from __future__ import annotations

from typing import Dict, Type

from ..interfaces import SourceConnector
from .base import ConnectorFactory
from .cloud_storage import CloudStorageConnector
from .google_workspace import GoogleWorkspaceConnector
from .microsoft_graph import MicrosoftGraphConnector
from .mock_email import MockEmailConnector


def build_default_factory() -> ConnectorFactory:
    registry: Dict[str, Type[SourceConnector]] = {
        "mock_email": MockEmailConnector,
        "microsoft_graph": MicrosoftGraphConnector,
        "google_workspace": GoogleWorkspaceConnector,
        "cloud_storage": CloudStorageConnector,
    }
    return ConnectorFactory(registry)
