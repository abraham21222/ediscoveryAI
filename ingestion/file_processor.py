"""
File processing pipeline for multimodal evidence.

This module analyzes files during ingestion and enriches them with:
- File type detection
- Corruption detection
- Quality assessment
- Preview capability flags
"""

from __future__ import annotations

import logging
from typing import List

from .file_analyzer import FileAnalyzer
from .interfaces import Processor
from .models import Attachment, EvidenceDocument

logger = logging.getLogger(__name__)


class FileAnalysisProcessor(Processor):
    """
    Processor that analyzes files for type, quality, and corruption.
    
    This processor:
    1. Analyzes each attachment using FileAnalyzer
    2. Enriches attachment metadata with analysis results
    3. Flags corrupted/encrypted files
    4. Enables filtering by file type in the UI
    """
    
    def __init__(self):
        """Initialize the file analysis processor."""
        self.analyzer = FileAnalyzer()
        self.stats = {
            'analyzed': 0,
            'corrupted': 0,
            'encrypted': 0,
            'valid': 0,
            'suspicious': 0,
        }
    
    def process(self, documents: List[EvidenceDocument]) -> List[EvidenceDocument]:
        """
        Process documents and analyze all attachments.
        
        Args:
            documents: List of evidence documents to process
            
        Returns:
            List of documents with enriched file analysis data
        """
        for document in documents:
            # Analyze each attachment
            for attachment in document.attachments:
                try:
                    analysis = self.analyzer.analyze_bytes(
                        filename=attachment.filename,
                        data=attachment.payload
                    )
                    
                    # Enrich attachment with analysis results
                    attachment.file_category = analysis.category.value
                    attachment.data_quality = analysis.quality.value
                    attachment.quality_details = analysis.quality_details
                    attachment.md5_hash = analysis.md5_hash
                    attachment.detected_mime = analysis.detected_mime
                    attachment.is_processable = analysis.is_processable
                    
                    # Update statistics
                    self.stats['analyzed'] += 1
                    if analysis.quality.value == 'corrupted':
                        self.stats['corrupted'] += 1
                    elif analysis.quality.value == 'encrypted':
                        self.stats['encrypted'] += 1
                    elif analysis.quality.value == 'valid':
                        self.stats['valid'] += 1
                    elif analysis.quality.value == 'suspicious':
                        self.stats['suspicious'] += 1
                    
                    # Log interesting findings
                    if not analysis.is_processable:
                        logger.warning(
                            f"Unprocessable file: {attachment.filename} - "
                            f"{analysis.quality.value}: {analysis.quality_details}"
                        )
                    
                except Exception as e:
                    logger.error(f"Error analyzing attachment {attachment.filename}: {e}")
                    # Mark as corrupted on analysis failure
                    attachment.data_quality = 'corrupted'
                    attachment.quality_details = f"Analysis failed: {str(e)}"
                    attachment.is_processable = False
                    self.stats['corrupted'] += 1
            
            # Log progress every 100 documents
            if self.stats['analyzed'] % 100 == 0 and self.stats['analyzed'] > 0:
                logger.info(
                    f"File analysis progress: {self.stats['analyzed']} files analyzed, "
                    f"{self.stats['corrupted']} corrupted, {self.stats['encrypted']} encrypted"
                )
        
        return documents
    
    def get_statistics(self) -> dict:
        """Get processing statistics."""
        return self.stats.copy()

