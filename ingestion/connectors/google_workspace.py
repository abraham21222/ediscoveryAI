"""Connector skeleton for Google Workspace (Gmail + Drive)."""

from __future__ import annotations

from typing import Iterable

from ..config import ConnectorConfig
from ..interfaces import SourceConnector
from ..models import EvidenceDocument


class GoogleWorkspaceConnector(SourceConnector):
    def __init__(self, config: ConnectorConfig) -> None:
        self._config = config
        self._service_account_file = config.params.get("service_account_file")
        self._subject_user = config.params.get("subject_user")
        self._batch_size = int(config.params.get("batch_size", 100))

    def fetch(self) -> Iterable[EvidenceDocument]:
        raise NotImplementedError(
            "Google Workspace integration should authenticate via service accounts with "
            "domain-wide delegation and iterate Gmail messages/Drive files with change tokens."
        )
