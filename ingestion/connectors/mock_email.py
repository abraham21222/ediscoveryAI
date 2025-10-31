"""Mock email connector producing deterministic sample documents."""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import Iterable, List

from ..config import ConnectorConfig
from ..interfaces import SourceConnector
from ..models import Attachment, Custodian, EvidenceDocument


class MockEmailConnector(SourceConnector):
    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._batch_size = int(config.params.get("batch_size", 10))

    def fetch(self) -> Iterable[EvidenceDocument]:
        base_time = datetime.utcnow() - timedelta(days=1)
        documents: List[EvidenceDocument] = []
        for idx in range(self._batch_size):
            subject = f"Project Falcon Update #{idx}"
            body = (
                "Team,\n\nAttached is the latest project status including risk flags."
                " Please review before tomorrow's standup.\n\nThanks,\nOps"
            )
            payload = body.encode("utf-8")
            checksum = sha256(payload).hexdigest()
            attachment = Attachment(
                filename="status.txt",
                content_type="text/plain",
                size_bytes=len(payload),
                payload=payload,
                checksum_sha256=checksum,
            )
            document = EvidenceDocument(
                document_id=f"mock-email-{idx}",
                source=self._config.name,
                collected_at=base_time + timedelta(minutes=idx),
                custodian=Custodian(identifier=f"custodian-{idx}", email=f"user{idx}@example.com"),
                subject=subject,
                body_text=body,
                raw_path=None,
                metadata={
                    "message_id": f"<mock-{idx}@example.com>",
                    "thread_id": "falcon-initiative",
                },
                attachments=[attachment],
            )
            documents.append(document)
        return documents
