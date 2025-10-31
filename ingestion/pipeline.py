"""High-level ingestion pipeline orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from .config import AppConfig, ConnectorConfig
from .connectors.registry import build_default_factory
from .interfaces import MetadataStore, ObjectStore, Processor, SourceConnector
from .models import EvidenceDocument
from .processors import build_processors
from .storage import build_metadata_store, build_object_store

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    connector_name: str
    processed_documents: int


class IngestionPipeline:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._connector_factory = build_default_factory()
        self._object_store: ObjectStore = build_object_store(config.object_store)
        self._metadata_store: MetadataStore = build_metadata_store(config.metadata_store)
        self._processors: List[Processor] = build_processors(config.processing)

    def run(self) -> List[IngestionResult]:
        results: List[IngestionResult] = []
        for connector_config in self._config.connectors:
            if not connector_config.enabled:
                logger.info("Skipping connector %s (disabled)", connector_config.name)
                continue
            connector = self._create_connector(connector_config)
            logger.info("Running connector %s", connector_config.name)
            documents = list(connector.fetch())
            documents = self._run_processors(documents)
            for document in documents:
                self._object_store.persist(document)
            self._metadata_store.bulk_index(documents)
            results.append(
                IngestionResult(
                    connector_name=connector_config.name,
                    processed_documents=len(documents),
                )
            )
            logger.info(
                "Connector %s finished, %d documents processed",
                connector_config.name,
                len(documents),
            )
        return results

    def _create_connector(self, connector_config: ConnectorConfig) -> SourceConnector:
        return self._connector_factory.create(connector_config)

    def _run_processors(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        processed = documents
        for processor in self._processors:
            processed = processor.process(processed)
        return processed
