"""Interface definitions for connectors, processors, and stores."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from .models import EvidenceDocument


class SourceConnector(ABC):
    """A connector capable of pulling raw evidence from an external system."""

    @abstractmethod
    def fetch(self) -> Iterable[EvidenceDocument]:
        """Yield evidence documents gathered from the source."""


class Processor(ABC):
    """A processing stage that mutates or enriches documents before persistence."""

    @abstractmethod
    def process(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        """Return processed documents."""


class ObjectStore(ABC):
    """Persists raw evidence payloads in immutable storage."""

    @abstractmethod
    def persist(self, document: EvidenceDocument) -> None:
        """Persist raw document payloads and attachments."""


class MetadataStore(ABC):
    """Indexes normalized metadata for search/filtering."""

    @abstractmethod
    def index(self, document: EvidenceDocument) -> None:
        """Insert or update metadata representation."""

    @abstractmethod
    def bulk_index(self, documents: List[EvidenceDocument]) -> None:
        """Efficient bulk write when supported."""
