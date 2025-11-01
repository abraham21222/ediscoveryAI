"""
File analysis and type detection for multimodal evidence ingestion.

This module provides:
- File type detection (MIME type, extension validation)
- Corruption detection (header validation, integrity checks)
- Metadata extraction (EXIF, document properties, etc.)
- Preview generation capability indicators
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class FileCategory(Enum):
    """High-level file categories for eDiscovery."""
    EMAIL = "email"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    ARCHIVE = "archive"
    DATABASE = "database"
    CODE = "code"
    UNKNOWN = "unknown"


class DataQuality(Enum):
    """Data quality assessment."""
    VALID = "valid"                    # File is intact and processable
    CORRUPTED = "corrupted"            # File header/structure is damaged
    ENCRYPTED = "encrypted"            # File is password-protected
    TRUNCATED = "truncated"            # File is incomplete (unexpected EOF)
    INVALID_FORMAT = "invalid_format"  # File extension doesn't match content
    SUSPICIOUS = "suspicious"          # Potential malware/suspicious patterns


@dataclass
class FileAnalysis:
    """Complete analysis result for a file."""
    
    # Basic file info
    filename: str
    file_size: int
    extension: str
    
    # Type detection
    mime_type: str
    detected_mime: Optional[str]  # MIME type from magic bytes
    category: FileCategory
    
    # Quality assessment
    quality: DataQuality
    quality_details: str
    is_processable: bool
    
    # Hashes for deduplication
    md5_hash: str
    sha256_hash: str
    
    # Extracted metadata
    metadata: Dict[str, str]
    
    # Preview capabilities
    supports_text_extraction: bool
    supports_image_preview: bool
    supports_thumbnail: bool
    
    # Analysis timestamp
    analyzed_at: datetime


# File signature magic bytes for validation
FILE_SIGNATURES = {
    # Documents
    b'%PDF': ('application/pdf', FileCategory.DOCUMENT),
    b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1': ('application/msword', FileCategory.DOCUMENT),  # DOC
    b'PK\x03\x04': ('application/zip', FileCategory.ARCHIVE),  # ZIP, DOCX, XLSX, etc.
    
    # Images
    b'\xff\xd8\xff': ('image/jpeg', FileCategory.IMAGE),
    b'\x89PNG\r\n\x1a\n': ('image/png', FileCategory.IMAGE),
    b'GIF87a': ('image/gif', FileCategory.IMAGE),
    b'GIF89a': ('image/gif', FileCategory.IMAGE),
    b'BM': ('image/bmp', FileCategory.IMAGE),
    b'II*\x00': ('image/tiff', FileCategory.IMAGE),
    b'MM\x00*': ('image/tiff', FileCategory.IMAGE),
    
    # Video
    b'\x00\x00\x00\x18ftypmp42': ('video/mp4', FileCategory.VIDEO),
    b'\x00\x00\x00\x1cftypmp42': ('video/mp4', FileCategory.VIDEO),
    b'RIFF': ('video/avi', FileCategory.VIDEO),  # AVI (need to check WAVE vs AVI)
    
    # Audio
    b'ID3': ('audio/mpeg', FileCategory.AUDIO),  # MP3
    b'\xff\xfb': ('audio/mpeg', FileCategory.AUDIO),  # MP3
    b'RIFF': ('audio/wav', FileCategory.AUDIO),  # WAV
    b'fLaC': ('audio/flac', FileCategory.AUDIO),
    
    # Archives
    b'\x50\x4b\x03\x04': ('application/zip', FileCategory.ARCHIVE),
    b'\x52\x61\x72\x21': ('application/x-rar-compressed', FileCategory.ARCHIVE),
    b'\x1f\x8b': ('application/gzip', FileCategory.ARCHIVE),
    b'7z\xbc\xaf\x27\x1c': ('application/x-7z-compressed', FileCategory.ARCHIVE),
    
    # Database
    b'SQLite format 3': ('application/x-sqlite3', FileCategory.DATABASE),
}


# MIME type to category mapping
MIME_TO_CATEGORY = {
    # Documents
    'application/pdf': FileCategory.DOCUMENT,
    'application/msword': FileCategory.DOCUMENT,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': FileCategory.DOCUMENT,
    'application/rtf': FileCategory.DOCUMENT,
    'text/plain': FileCategory.DOCUMENT,
    'text/html': FileCategory.DOCUMENT,
    
    # Spreadsheets
    'application/vnd.ms-excel': FileCategory.SPREADSHEET,
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileCategory.SPREADSHEET,
    'text/csv': FileCategory.SPREADSHEET,
    
    # Presentations
    'application/vnd.ms-powerpoint': FileCategory.PRESENTATION,
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': FileCategory.PRESENTATION,
    
    # Email
    'message/rfc822': FileCategory.EMAIL,
    'application/vnd.ms-outlook': FileCategory.EMAIL,
    
    # Images
    'image/jpeg': FileCategory.IMAGE,
    'image/png': FileCategory.IMAGE,
    'image/gif': FileCategory.IMAGE,
    'image/bmp': FileCategory.IMAGE,
    'image/tiff': FileCategory.IMAGE,
    'image/svg+xml': FileCategory.IMAGE,
    'image/webp': FileCategory.IMAGE,
    
    # Video
    'video/mp4': FileCategory.VIDEO,
    'video/mpeg': FileCategory.VIDEO,
    'video/quicktime': FileCategory.VIDEO,
    'video/x-msvideo': FileCategory.VIDEO,
    'video/x-matroska': FileCategory.VIDEO,
    
    # Audio
    'audio/mpeg': FileCategory.AUDIO,
    'audio/wav': FileCategory.AUDIO,
    'audio/ogg': FileCategory.AUDIO,
    'audio/flac': FileCategory.AUDIO,
    'audio/mp4': FileCategory.AUDIO,
    
    # Archives
    'application/zip': FileCategory.ARCHIVE,
    'application/x-rar-compressed': FileCategory.ARCHIVE,
    'application/gzip': FileCategory.ARCHIVE,
    'application/x-7z-compressed': FileCategory.ARCHIVE,
    'application/x-tar': FileCategory.ARCHIVE,
    
    # Database
    'application/x-sqlite3': FileCategory.DATABASE,
    'application/vnd.ms-access': FileCategory.DATABASE,
}


class FileAnalyzer:
    """Analyzes files for type, quality, and processability."""
    
    def __init__(self):
        """Initialize the file analyzer."""
        # Initialize mimetypes database
        mimetypes.init()
    
    def analyze_file(self, filepath: Path) -> FileAnalysis:
        """
        Perform complete analysis of a file.
        
        Args:
            filepath: Path to the file to analyze
            
        Returns:
            FileAnalysis object with complete analysis results
        """
        try:
            # Basic file info
            filename = filepath.name
            file_size = filepath.stat().st_size if filepath.exists() else 0
            extension = filepath.suffix.lower()
            
            # Read file for analysis
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            # Compute hashes
            md5_hash = hashlib.md5(file_data).hexdigest()
            sha256_hash = hashlib.sha256(file_data).hexdigest()
            
            # Detect MIME type
            mime_type = self._guess_mime_from_extension(filepath)
            detected_mime = self._detect_mime_from_magic(file_data)
            
            # Determine category
            category = self._determine_category(mime_type, detected_mime, extension)
            
            # Quality assessment
            quality, quality_details = self._assess_quality(
                file_data, filepath, mime_type, detected_mime
            )
            
            # Check if processable
            is_processable = (
                quality in [DataQuality.VALID, DataQuality.SUSPICIOUS] 
                and file_size > 0
            )
            
            # Extract metadata
            metadata = self._extract_metadata(file_data, category, filepath)
            
            # Determine preview capabilities
            supports_text = self._supports_text_extraction(category, quality)
            supports_image = self._supports_image_preview(category, quality)
            supports_thumb = self._supports_thumbnail(category, quality)
            
            return FileAnalysis(
                filename=filename,
                file_size=file_size,
                extension=extension,
                mime_type=mime_type,
                detected_mime=detected_mime,
                category=category,
                quality=quality,
                quality_details=quality_details,
                is_processable=is_processable,
                md5_hash=md5_hash,
                sha256_hash=sha256_hash,
                metadata=metadata,
                supports_text_extraction=supports_text,
                supports_image_preview=supports_image,
                supports_thumbnail=supports_thumb,
                analyzed_at=datetime.utcnow(),
            )
            
        except Exception as e:
            logger.error(f"Error analyzing file {filepath}: {e}")
            # Return minimal analysis on error
            return self._create_error_analysis(filepath, str(e))
    
    def analyze_bytes(self, filename: str, data: bytes) -> FileAnalysis:
        """
        Analyze file from bytes without filesystem access.
        
        Args:
            filename: Original filename
            data: File contents as bytes
            
        Returns:
            FileAnalysis object
        """
        try:
            file_size = len(data)
            extension = Path(filename).suffix.lower()
            
            # Compute hashes
            md5_hash = hashlib.md5(data).hexdigest()
            sha256_hash = hashlib.sha256(data).hexdigest()
            
            # Detect MIME type
            mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            detected_mime = self._detect_mime_from_magic(data)
            
            # Determine category
            category = self._determine_category(mime_type, detected_mime, extension)
            
            # Quality assessment
            quality, quality_details = self._assess_quality_from_bytes(
                data, filename, mime_type, detected_mime
            )
            
            is_processable = (
                quality in [DataQuality.VALID, DataQuality.SUSPICIOUS] 
                and file_size > 0
            )
            
            metadata = self._extract_metadata_from_bytes(data, category, filename)
            
            return FileAnalysis(
                filename=filename,
                file_size=file_size,
                extension=extension,
                mime_type=mime_type,
                detected_mime=detected_mime,
                category=category,
                quality=quality,
                quality_details=quality_details,
                is_processable=is_processable,
                md5_hash=md5_hash,
                sha256_hash=sha256_hash,
                metadata=metadata,
                supports_text_extraction=self._supports_text_extraction(category, quality),
                supports_image_preview=self._supports_image_preview(category, quality),
                supports_thumbnail=self._supports_thumbnail(category, quality),
                analyzed_at=datetime.utcnow(),
            )
            
        except Exception as e:
            logger.error(f"Error analyzing bytes for {filename}: {e}")
            return self._create_error_analysis_from_name(filename, str(e))
    
    def _guess_mime_from_extension(self, filepath: Path) -> str:
        """Guess MIME type from file extension."""
        mime_type, _ = mimetypes.guess_type(str(filepath))
        return mime_type or 'application/octet-stream'
    
    def _detect_mime_from_magic(self, data: bytes) -> Optional[str]:
        """Detect MIME type from file magic bytes."""
        # Check known signatures
        for signature, (mime_type, _) in FILE_SIGNATURES.items():
            if data.startswith(signature):
                return mime_type
        
        # Check for ZIP-based formats (DOCX, XLSX, PPTX)
        if data.startswith(b'PK\x03\x04'):
            # Check for Office Open XML formats
            if b'word/' in data[:4096]:
                return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif b'xl/' in data[:4096]:
                return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif b'ppt/' in data[:4096]:
                return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        
        return None
    
    def _determine_category(
        self, mime_type: str, detected_mime: Optional[str], extension: str
    ) -> FileCategory:
        """Determine file category from MIME type and extension."""
        # Try detected MIME first
        if detected_mime and detected_mime in MIME_TO_CATEGORY:
            return MIME_TO_CATEGORY[detected_mime]
        
        # Try declared MIME type
        if mime_type in MIME_TO_CATEGORY:
            return MIME_TO_CATEGORY[mime_type]
        
        # Fallback to extension-based detection
        if extension in {'.doc', '.docx', '.pdf', '.txt', '.rtf', '.odt'}:
            return FileCategory.DOCUMENT
        elif extension in {'.xls', '.xlsx', '.csv', '.ods'}:
            return FileCategory.SPREADSHEET
        elif extension in {'.ppt', '.pptx', '.odp'}:
            return FileCategory.PRESENTATION
        elif extension in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg', '.webp'}:
            return FileCategory.IMAGE
        elif extension in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}:
            return FileCategory.VIDEO
        elif extension in {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.wma'}:
            return FileCategory.AUDIO
        elif extension in {'.zip', '.rar', '.7z', '.tar', '.gz', '.bz2'}:
            return FileCategory.ARCHIVE
        elif extension in {'.eml', '.msg', '.mbox'}:
            return FileCategory.EMAIL
        elif extension in {'.db', '.sqlite', '.mdb', '.accdb'}:
            return FileCategory.DATABASE
        elif extension in {'.py', '.java', '.cpp', '.js', '.go', '.rs'}:
            return FileCategory.CODE
        
        return FileCategory.UNKNOWN
    
    def _assess_quality(
        self, data: bytes, filepath: Path, mime_type: str, detected_mime: Optional[str]
    ) -> Tuple[DataQuality, str]:
        """Assess file quality and integrity."""
        return self._assess_quality_from_bytes(data, filepath.name, mime_type, detected_mime)
    
    def _assess_quality_from_bytes(
        self, data: bytes, filename: str, mime_type: str, detected_mime: Optional[str]
    ) -> Tuple[DataQuality, str]:
        """Assess file quality from bytes."""
        # Check if file is empty
        if len(data) == 0:
            return DataQuality.CORRUPTED, "File is empty"
        
        # Check for MIME type mismatch
        if detected_mime and mime_type != 'application/octet-stream':
            if not self._mime_types_compatible(mime_type, detected_mime):
                return DataQuality.INVALID_FORMAT, f"Extension suggests {mime_type} but content is {detected_mime}"
        
        # Check for encryption/password protection
        if self._is_encrypted(data, filename):
            return DataQuality.ENCRYPTED, "File appears to be password-protected"
        
        # Check for corruption based on file type
        if detected_mime:
            corruption_check = self._check_corruption(data, detected_mime)
            if corruption_check:
                return DataQuality.CORRUPTED, corruption_check
        
        # Check for suspicious patterns (basic malware detection)
        if self._is_suspicious(data):
            return DataQuality.SUSPICIOUS, "File contains suspicious patterns"
        
        return DataQuality.VALID, "File appears intact"
    
    def _mime_types_compatible(self, mime1: str, mime2: str) -> bool:
        """Check if two MIME types are compatible (e.g., both are archives)."""
        # Exact match
        if mime1 == mime2:
            return True
        
        # Both are archives
        archives = {'application/zip', 'application/x-zip-compressed'}
        if mime1 in archives and mime2 in archives:
            return True
        
        # Both are Office documents (older vs newer formats)
        if 'officedocument' in mime1 and 'ms-' in mime2:
            return True
        if 'officedocument' in mime2 and 'ms-' in mime1:
            return True
        
        return False
    
    def _is_encrypted(self, data: bytes, filename: str) -> bool:
        """Check if file is encrypted or password-protected."""
        # PDF encryption
        if data.startswith(b'%PDF') and b'/Encrypt' in data[:4096]:
            return True
        
        # Office document encryption (check for EncryptedPackage)
        if b'EncryptedPackage' in data[:4096]:
            return True
        
        # ZIP encryption
        if data.startswith(b'PK\x03\x04'):
            # Check encryption bit in ZIP header (byte 6-7)
            if len(data) >= 8 and (data[6] & 0x01):
                return True
        
        return False
    
    def _check_corruption(self, data: bytes, mime_type: str) -> Optional[str]:
        """Check for file corruption based on MIME type."""
        # PDF corruption check
        if mime_type == 'application/pdf':
            if not data.endswith(b'%%EOF\n') and not data.endswith(b'%%EOF'):
                return "PDF missing EOF marker (possibly truncated)"
        
        # ZIP corruption check
        if 'zip' in mime_type.lower():
            if len(data) < 22:  # Minimum ZIP file size
                return "ZIP file too small (corrupted)"
        
        # JPEG corruption check
        if mime_type == 'image/jpeg':
            if not data.endswith(b'\xff\xd9'):
                return "JPEG missing EOI marker (possibly truncated)"
        
        # PNG corruption check
        if mime_type == 'image/png':
            if not data.endswith(b'\x00\x00\x00\x00IEND\xae\x42\x60\x82'):
                return "PNG missing IEND chunk (possibly truncated)"
        
        return None
    
    def _is_suspicious(self, data: bytes) -> bool:
        """Basic check for suspicious file patterns."""
        # Look for common malware indicators
        suspicious_patterns = [
            b'TVqQAAMAAAAEAAAA',  # PE executable in base64
            b'This program cannot be run in DOS mode',
            b'<script',  # Embedded scripts in unexpected files
        ]
        
        for pattern in suspicious_patterns:
            if pattern in data[:8192]:  # Check first 8KB
                return True
        
        return False
    
    def _extract_metadata(self, data: bytes, category: FileCategory, filepath: Path) -> Dict[str, str]:
        """Extract metadata from file."""
        return self._extract_metadata_from_bytes(data, category, filepath.name)
    
    def _extract_metadata_from_bytes(self, data: bytes, category: FileCategory, filename: str) -> Dict[str, str]:
        """Extract metadata from file bytes."""
        metadata = {}
        
        # PDF metadata extraction
        if category == FileCategory.DOCUMENT and data.startswith(b'%PDF'):
            metadata['pdf_version'] = self._extract_pdf_version(data)
        
        # Image dimensions (basic)
        if category == FileCategory.IMAGE:
            dimensions = self._extract_image_dimensions(data)
            if dimensions:
                metadata['width'], metadata['height'] = dimensions
        
        return metadata
    
    def _extract_pdf_version(self, data: bytes) -> str:
        """Extract PDF version from header."""
        try:
            header = data[:20].decode('ascii', errors='ignore')
            if '%PDF-' in header:
                version = header.split('%PDF-')[1][:3]
                return version
        except:
            pass
        return 'unknown'
    
    def _extract_image_dimensions(self, data: bytes) -> Optional[Tuple[str, str]]:
        """Extract image dimensions (basic implementation)."""
        # PNG dimensions
        if data.startswith(b'\x89PNG'):
            if len(data) >= 24:
                width = int.from_bytes(data[16:20], 'big')
                height = int.from_bytes(data[20:24], 'big')
                return str(width), str(height)
        
        # JPEG dimensions (simplified)
        # This is complex, would need full JPEG parser in production
        
        return None
    
    def _supports_text_extraction(self, category: FileCategory, quality: DataQuality) -> bool:
        """Check if text extraction is supported."""
        if quality != DataQuality.VALID:
            return False
        return category in {
            FileCategory.DOCUMENT,
            FileCategory.EMAIL,
            FileCategory.SPREADSHEET,
            FileCategory.PRESENTATION,
            FileCategory.CODE,
        }
    
    def _supports_image_preview(self, category: FileCategory, quality: DataQuality) -> bool:
        """Check if image preview is supported."""
        if quality != DataQuality.VALID:
            return False
        return category in {FileCategory.IMAGE, FileCategory.VIDEO}
    
    def _supports_thumbnail(self, category: FileCategory, quality: DataQuality) -> bool:
        """Check if thumbnail generation is supported."""
        if quality != DataQuality.VALID:
            return False
        return category in {
            FileCategory.IMAGE,
            FileCategory.VIDEO,
            FileCategory.DOCUMENT,
            FileCategory.PRESENTATION,
        }
    
    def _create_error_analysis(self, filepath: Path, error: str) -> FileAnalysis:
        """Create minimal analysis result for error case."""
        return FileAnalysis(
            filename=filepath.name,
            file_size=0,
            extension=filepath.suffix.lower(),
            mime_type='application/octet-stream',
            detected_mime=None,
            category=FileCategory.UNKNOWN,
            quality=DataQuality.CORRUPTED,
            quality_details=f"Analysis failed: {error}",
            is_processable=False,
            md5_hash='',
            sha256_hash='',
            metadata={},
            supports_text_extraction=False,
            supports_image_preview=False,
            supports_thumbnail=False,
            analyzed_at=datetime.utcnow(),
        )
    
    def _create_error_analysis_from_name(self, filename: str, error: str) -> FileAnalysis:
        """Create minimal analysis result for error case from filename."""
        return FileAnalysis(
            filename=filename,
            file_size=0,
            extension=Path(filename).suffix.lower(),
            mime_type='application/octet-stream',
            detected_mime=None,
            category=FileCategory.UNKNOWN,
            quality=DataQuality.CORRUPTED,
            quality_details=f"Analysis failed: {error}",
            is_processable=False,
            md5_hash='',
            sha256_hash='',
            metadata={},
            supports_text_extraction=False,
            supports_image_preview=False,
            supports_thumbnail=False,
            analyzed_at=datetime.utcnow(),
        )


# Convenience function
def analyze_file(filepath: Path) -> FileAnalysis:
    """Analyze a file and return complete analysis."""
    analyzer = FileAnalyzer()
    return analyzer.analyze_file(filepath)


def analyze_bytes(filename: str, data: bytes) -> FileAnalysis:
    """Analyze file bytes and return complete analysis."""
    analyzer = FileAnalyzer()
    return analyzer.analyze_bytes(filename, data)

