"""Connector skeleton for cloud object stores like S3 or Azure Blob."""

from __future__ import annotations

from typing import Iterable

from ..config import ConnectorConfig
from ..interfaces import SourceConnector
from ..models import EvidenceDocument


class CloudStorageConnector(SourceConnector):
    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._provider = config.params.get("provider", "aws_s3")
        self._bucket = config.params.get("bucket")
        self._prefix = config.params.get("prefix", "")

    def fetch(self) -> Iterable[EvidenceDocument]:
        raise NotImplementedError(
            "Cloud storage ingestion must stream objects, compute checksums, and attach metadata "
            "(etag, last_modified). Provide credentials and bucket details to enable this."
        )
