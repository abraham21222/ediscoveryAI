"""Utilities shared across connector implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Type

from ..config import ConnectorConfig
from ..interfaces import SourceConnector


@dataclass
class ConnectorFactory:
    """Registry-backed factory for connector instances."""

    registry: Dict[str, Type[SourceConnector]]

    def create(self, config: ConnectorConfig) -> SourceConnector:
        try:
            connector_cls = self.registry[config.type]
        except KeyError as exc:
            raise ValueError(f"Unknown connector type: {config.type}") from exc
        return connector_cls(config)
