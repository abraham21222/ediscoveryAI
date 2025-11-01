"""Domain models used throughout the ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class Custodian:
    identifier: str
    display_name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class Attachment:
    filename: str
    content_type: Optional[str]
    size_bytes: int
    payload: bytes = field(repr=False)
    checksum_sha256: Optional[str] = None
    # File analysis fields
    file_category: Optional[str] = None  # document, image, video, etc.
    data_quality: Optional[str] = None  # valid, corrupted, encrypted, etc.
    quality_details: Optional[str] = None
    md5_hash: Optional[str] = None
    detected_mime: Optional[str] = None  # MIME from magic bytes
    is_processable: bool = True


@dataclass
class ChainOfCustodyEvent:
    timestamp: datetime
    actor: str
    action: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceDocument:
    document_id: str
    source: str
    collected_at: datetime
    custodian: Custodian
    subject: Optional[str]
    body_text: Optional[str]
    raw_path: Optional[str]
    metadata: Dict[str, str] = field(default_factory=dict)
    attachments: List[Attachment] = field(default_factory=list)
    chain_of_custody: List[ChainOfCustodyEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "document_id": self.document_id,
            "source": self.source,
            "collected_at": self.collected_at.isoformat(),
            "custodian": {
                "identifier": self.custodian.identifier,
                "display_name": self.custodian.display_name,
                "email": self.custodian.email,
            },
            "subject": self.subject,
            "body_text": self.body_text,
            "raw_path": self.raw_path,
            "metadata": self.metadata,
            "attachments": [
                {
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size_bytes": attachment.size_bytes,
                    "checksum_sha256": attachment.checksum_sha256,
                    "file_category": attachment.file_category,
                    "data_quality": attachment.data_quality,
                    "quality_details": attachment.quality_details,
                    "md5_hash": attachment.md5_hash,
                    "detected_mime": attachment.detected_mime,
                    "is_processable": attachment.is_processable,
                }
                for attachment in self.attachments
            ],
            "chain_of_custody": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor,
                    "action": event.action,
                    "metadata": event.metadata,
                }
                for event in self.chain_of_custody
            ],
        }
