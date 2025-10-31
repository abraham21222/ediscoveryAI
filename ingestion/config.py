"""Configuration models and helpers for the ingestion service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import json


@dataclass
class ConnectorConfig:
    """Generic connector configuration."""

    type: str
    name: str
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingConfig:
    """Toggleable processing stages."""

    enable_deduplication: bool = True
    enable_ocr: bool = True
    enable_entity_extraction: bool = True
    enable_privilege_detection: bool = False


@dataclass
class StorageTargetConfig:
    """Storage settings for object and metadata stores."""

    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """Security controls to enforce across the pipeline."""

    envelope_encryption: bool = True
    key_management_service: Optional[str] = None
    rbac_policy: Optional[str] = None
    audit_log_destination: Optional[str] = None


@dataclass
class AppConfig:
    """Top-level configuration for the ingestion pipeline."""

    connectors: List[ConnectorConfig]
    object_store: StorageTargetConfig
    metadata_store: StorageTargetConfig
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        connectors = [ConnectorConfig(**item) for item in data.get("connectors", [])]
        object_store = StorageTargetConfig(**data["object_store"])
        metadata_store = StorageTargetConfig(**data["metadata_store"])
        processing = ProcessingConfig(**data.get("processing", {}))
        security = SecurityConfig(**data.get("security", {}))
        return cls(
            connectors=connectors,
            object_store=object_store,
            metadata_store=metadata_store,
            processing=processing,
            security=security,
        )

    @classmethod
    def from_json(cls, path: Path) -> "AppConfig":
        data = json.loads(path.read_text())
        return cls.from_dict(data)


DEFAULT_CONFIG = AppConfig(
    connectors=[
        ConnectorConfig(type="mock_email", name="sample_m365_mailbox", enabled=True, params={"batch_size": 50}),
    ],
    object_store=StorageTargetConfig(type="local_fs", params={"base_path": "./_evidence"}),
    metadata_store=StorageTargetConfig(type="sqlite", params={"path": "./_metadata/metadata.db"}),
)
