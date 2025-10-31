"""Processing stage implementations used by the ingestion pipeline."""

from __future__ import annotations

from hashlib import sha256
from typing import List, Set

from .config import ProcessingConfig
from .interfaces import Processor
from .models import EvidenceDocument


class DeduplicationProcessor(Processor):
    def __init__(self) -> None:
        self._seen_hashes: Set[str] = set()

    def process(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        unique: List[EvidenceDocument] = []
        for doc in documents:
            content = (doc.subject or "") + (doc.body_text or "")
            digest = sha256(content.encode("utf-8")).hexdigest()
            if digest in self._seen_hashes:
                continue
            self._seen_hashes.add(digest)
            doc.metadata.setdefault("hash_sha256", digest)
            unique.append(doc)
        return unique


class OCRProcessor(Processor):
    def process(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        for doc in documents:
            doc.metadata.setdefault("ocr_status", "skipped_mock")
        return documents


class EntityExtractionProcessor(Processor):
    def process(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        for doc in documents:
            doc.metadata.setdefault("entities", [])
        return documents


class PrivilegeDetectionProcessor(Processor):
    def process(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        for doc in documents:
            doc.metadata.setdefault("privilege_score", 0.0)
        return documents


def build_processors(config: ProcessingConfig) -> List[Processor]:
    processors: List[Processor] = []
    if config.enable_deduplication:
        processors.append(DeduplicationProcessor())
    if config.enable_ocr:
        processors.append(OCRProcessor())
    if config.enable_entity_extraction:
        processors.append(EntityExtractionProcessor())
    if config.enable_privilege_detection:
        processors.append(PrivilegeDetectionProcessor())
    return processors
