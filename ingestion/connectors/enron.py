"""
Enron Email Dataset Connector

Ingests Enron emails from the sample dataset for testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from typing import Iterable, List
from ..config import ConnectorConfig
from ..interfaces import SourceConnector
from ..models import EvidenceDocument, Custodian


class EnronConnector(SourceConnector):
    """Connector for Enron email dataset."""
    
    def __init__(self, config: ConnectorConfig):
        """
        Initialize Enron connector.
        
        Args:
            config: Connector configuration
        """
        self._config = config
        data_path = config.params.get('data_path', 'data/enron/sample')
        self.data_path = Path(data_path)
    
    def fetch(self) -> Iterable[EvidenceDocument]:
        """
        Fetch Enron emails and yield as EvidenceDocuments.
        
        Returns:
            List of EvidenceDocument instances
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"Enron data path not found: {self.data_path}")
        
        # Get all JSON email files
        email_files = sorted(self.data_path.glob("*.json"))
        
        print(f"📧 Found {len(email_files)} Enron emails to ingest")
        
        documents: List[EvidenceDocument] = []
        
        for email_file in email_files:
            try:
                with open(email_file) as f:
                    email_data = json.load(f)
                
                # Parse date
                date_str = email_data.get('date', '')
                try:
                    if date_str:
                        timestamp = datetime.strptime(date_str, '%Y-%m-%d')
                    else:
                        timestamp = datetime.utcnow()
                except:
                    timestamp = datetime.utcnow()
                
                # Extract custodian from sender
                sender = email_data.get('from', 'unknown@enron.com')
                custodian_email = sender.strip().lower()
                custodian_identifier = custodian_email.split('@')[0]
                custodian_name = custodian_identifier.replace('.', ' ').title()
                
                # Build custodian
                custodian = Custodian(
                    identifier=custodian_identifier,
                    display_name=custodian_name,
                    email=custodian_email
                )
                
                # Build document
                doc = EvidenceDocument(
                    document_id=f"enron-{email_file.stem}",
                    source=self._config.name,
                    collected_at=timestamp,
                    custodian=custodian,
                    subject=email_data.get('subject', 'No Subject'),
                    body_text=email_data.get('body', ''),
                    raw_path=None,
                    metadata={
                        "from": email_data.get('from', ''),
                        "to": email_data.get('to', ''),
                        "date": email_data.get('date', ''),
                        "dataset": "enron",
                        "custodian_type": "executive" if any(name in custodian_email for name in ['lay', 'skilling', 'fastow']) else "employee"
                    }
                )
                
                documents.append(doc)
                
            except Exception as e:
                print(f"⚠️  Error processing {email_file}: {e}")
                continue
        
        return documents

