"""Storage backends for evidence payloads and metadata."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import boto3
import psycopg2
import psycopg2.pool
import psycopg2.extras
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import StorageTargetConfig
from .interfaces import MetadataStore, ObjectStore
from .models import ChainOfCustodyEvent, EvidenceDocument

logger = logging.getLogger(__name__)


class LocalFilesystemObjectStore(ObjectStore):
    def __init__(self, config: StorageTargetConfig) -> None:
        base_path = config.params.get("base_path")
        if not base_path:
            raise ValueError("LocalFilesystemObjectStore requires base_path param")
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def persist(self, document: EvidenceDocument) -> None:
        doc_dir = self._base_path / document.source / document.document_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        if document.body_text:
            (doc_dir / "body.txt").write_text(document.body_text, encoding="utf-8")
        if document.metadata:
            (doc_dir / "metadata.json").write_text(json.dumps(document.metadata, indent=2), encoding="utf-8")
        for attachment in document.attachments:
            target = doc_dir / attachment.filename
            target.write_bytes(attachment.payload)


class S3ObjectStore(ObjectStore):
    """
    Production-grade S3 object store with per-tenant bucket isolation.
    
    Features:
    - Per-tenant bucket isolation for data segregation
    - Multipart uploads for files >5MB
    - Automatic retries with exponential backoff
    - Chain of custody tracking via S3 object metadata
    - Server-side encryption (SSE-KMS or SSE-S3)
    - Immutable storage with versioning support
    """
    
    # Multipart upload threshold (5MB minimum per AWS requirements)
    MULTIPART_THRESHOLD = 5 * 1024 * 1024  # 5 MB
    MULTIPART_CHUNKSIZE = 8 * 1024 * 1024  # 8 MB per part
    
    def __init__(self, config: StorageTargetConfig) -> None:
        """
        Initialize S3 object store.
        
        Required params:
        - tenant_id: Unique identifier for the tenant/organization
        - bucket_prefix: Prefix for bucket naming (e.g., 'ediscovery-prod')
        
        Optional params:
        - region: AWS region (default: us-east-1)
        - kms_key_id: KMS key ARN for encryption (if not provided, uses SSE-S3)
        - endpoint_url: Custom S3 endpoint (for LocalStack testing)
        - enable_versioning: Enable S3 versioning (default: True)
        - storage_class: S3 storage class (default: STANDARD)
        """
        self._validate_config(config)
        
        self._tenant_id = config.params["tenant_id"]
        self._bucket_prefix = config.params["bucket_prefix"]
        self._region = config.params.get("region", "us-east-1")
        self._kms_key_id = config.params.get("kms_key_id")
        self._storage_class = config.params.get("storage_class", "STANDARD")
        self._enable_versioning = config.params.get("enable_versioning", True)
        
        # Initialize boto3 client
        endpoint_url = config.params.get("endpoint_url")  # For LocalStack
        self._s3_client = boto3.client(
            "s3",
            region_name=self._region,
            endpoint_url=endpoint_url,
        )
        
        # Construct bucket name: {prefix}-{tenant_id}
        # e.g., ediscovery-prod-acme-corp
        self._bucket_name = f"{self._bucket_prefix}-{self._tenant_id}"
        
        # Ensure bucket exists and is configured
        self._ensure_bucket_configured()
        
        logger.info(
            "Initialized S3ObjectStore for tenant=%s, bucket=%s, region=%s",
            self._tenant_id,
            self._bucket_name,
            self._region,
        )
    
    def _validate_config(self, config: StorageTargetConfig) -> None:
        """Validate required configuration parameters."""
        required = ["tenant_id", "bucket_prefix"]
        for param in required:
            if param not in config.params:
                raise ValueError(f"S3ObjectStore requires '{param}' in params")
    
    def _ensure_bucket_configured(self) -> None:
        """Ensure the S3 bucket exists and is properly configured."""
        try:
            # Check if bucket exists
            self._s3_client.head_bucket(Bucket=self._bucket_name)
            logger.debug("Bucket %s already exists", self._bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                # Bucket doesn't exist, create it
                self._create_bucket()
            else:
                raise
        
        # Configure versioning if enabled
        if self._enable_versioning:
            self._enable_bucket_versioning()
    
    def _create_bucket(self) -> None:
        """Create the S3 bucket with proper configuration."""
        try:
            create_bucket_config = {}
            # For regions other than us-east-1, we need LocationConstraint
            if self._region != "us-east-1":
                create_bucket_config["CreateBucketConfiguration"] = {
                    "LocationConstraint": self._region
                }
            
            self._s3_client.create_bucket(
                Bucket=self._bucket_name,
                **create_bucket_config,
            )
            logger.info("Created S3 bucket: %s", self._bucket_name)
            
            # Enable default encryption
            self._enable_bucket_encryption()
            
            # Block public access
            self._block_public_access()
            
        except ClientError as e:
            logger.error("Failed to create bucket %s: %s", self._bucket_name, e)
            raise
    
    def _enable_bucket_encryption(self) -> None:
        """Enable default encryption for the bucket."""
        encryption_config = {
            "Rules": [
                {
                    "ApplyServerSideEncryptionByDefault": {},
                    "BucketKeyEnabled": True,
                }
            ]
        }
        
        if self._kms_key_id:
            # Use KMS encryption with customer-managed key
            encryption_config["Rules"][0]["ApplyServerSideEncryptionByDefault"] = {
                "SSEAlgorithm": "aws:kms",
                "KMSMasterKeyID": self._kms_key_id,
            }
        else:
            # Use S3-managed encryption
            encryption_config["Rules"][0]["ApplyServerSideEncryptionByDefault"] = {
                "SSEAlgorithm": "AES256",
            }
        
        try:
            self._s3_client.put_bucket_encryption(
                Bucket=self._bucket_name,
                ServerSideEncryptionConfiguration=encryption_config,
            )
            logger.info("Enabled encryption for bucket: %s", self._bucket_name)
        except ClientError as e:
            logger.warning("Failed to enable encryption: %s", e)
    
    def _block_public_access(self) -> None:
        """Block all public access to the bucket."""
        try:
            self._s3_client.put_public_access_block(
                Bucket=self._bucket_name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True,
                    "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True,
                    "RestrictPublicBuckets": True,
                },
            )
            logger.info("Blocked public access for bucket: %s", self._bucket_name)
        except ClientError as e:
            logger.warning("Failed to block public access: %s", e)
    
    def _enable_bucket_versioning(self) -> None:
        """Enable versioning for immutable storage."""
        try:
            self._s3_client.put_bucket_versioning(
                Bucket=self._bucket_name,
                VersioningConfiguration={"Status": "Enabled"},
            )
            logger.debug("Enabled versioning for bucket: %s", self._bucket_name)
        except ClientError as e:
            logger.warning("Failed to enable versioning: %s", e)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def persist(self, document: EvidenceDocument) -> None:
        """
        Persist evidence document to S3.
        
        Object key structure:
        {source}/{matter_id}/{document_id}/body.txt
        {source}/{matter_id}/{document_id}/metadata.json
        {source}/{matter_id}/{document_id}/attachments/{filename}
        {source}/{matter_id}/{document_id}/custody_chain.json
        """
        try:
            # Extract matter_id from metadata or use 'default'
            matter_id = document.metadata.get("matter_id", "default")
            
            # Build base key prefix
            base_key = f"{document.source}/{matter_id}/{document.document_id}"
            
            # Persist body text
            if document.body_text:
                body_key = f"{base_key}/body.txt"
                self._upload_object(
                    key=body_key,
                    content=document.body_text.encode("utf-8"),
                    content_type="text/plain",
                    metadata=self._build_object_metadata(document, "body"),
                )
            
            # Persist metadata JSON
            metadata_key = f"{base_key}/metadata.json"
            metadata_content = json.dumps(document.to_dict(), indent=2)
            self._upload_object(
                key=metadata_key,
                content=metadata_content.encode("utf-8"),
                content_type="application/json",
                metadata=self._build_object_metadata(document, "metadata"),
            )
            
            # Persist attachments
            for attachment in document.attachments:
                attachment_key = f"{base_key}/attachments/{attachment.filename}"
                self._upload_object(
                    key=attachment_key,
                    content=attachment.payload,
                    content_type=attachment.content_type or "application/octet-stream",
                    metadata=self._build_object_metadata(document, "attachment", attachment.filename),
                )
            
            # Persist chain of custody as separate immutable log
            custody_key = f"{base_key}/custody_chain.json"
            custody_content = json.dumps(
                [
                    {
                        "timestamp": event.timestamp.isoformat(),
                        "actor": event.actor,
                        "action": event.action,
                        "metadata": event.metadata,
                    }
                    for event in document.chain_of_custody
                ],
                indent=2,
            )
            self._upload_object(
                key=custody_key,
                content=custody_content.encode("utf-8"),
                content_type="application/json",
                metadata=self._build_object_metadata(document, "custody_chain"),
            )
            
            # Add chain of custody event for S3 persistence
            document.chain_of_custody.append(
                ChainOfCustodyEvent(
                    timestamp=datetime.utcnow(),
                    actor="s3_object_store",
                    action="persisted_to_s3",
                    metadata={
                        "bucket": self._bucket_name,
                        "base_key": base_key,
                        "region": self._region,
                    },
                )
            )
            
            logger.info(
                "Successfully persisted document %s to S3: %s",
                document.document_id,
                base_key,
            )
            
        except Exception as e:
            logger.error(
                "Failed to persist document %s: %s",
                document.document_id,
                e,
            )
            raise
    
    def _upload_object(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Dict[str, str],
    ) -> None:
        """Upload object to S3 with multipart support for large files."""
        content_length = len(content)
        
        # Use multipart upload for large files
        if content_length > self.MULTIPART_THRESHOLD:
            self._multipart_upload(key, content, content_type, metadata)
        else:
            self._simple_upload(key, content, content_type, metadata)
    
    def _simple_upload(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Dict[str, str],
    ) -> None:
        """Simple S3 PUT for small files."""
        put_params = {
            "Bucket": self._bucket_name,
            "Key": key,
            "Body": content,
            "ContentType": content_type,
            "Metadata": metadata,
            "StorageClass": self._storage_class,
        }
        
        # Add encryption if KMS key is configured
        if self._kms_key_id:
            put_params["ServerSideEncryption"] = "aws:kms"
            put_params["SSEKMSKeyId"] = self._kms_key_id
        
        self._s3_client.put_object(**put_params)
        logger.debug("Uploaded %s (%d bytes) to S3", key, len(content))
    
    def _multipart_upload(
        self,
        key: str,
        content: bytes,
        content_type: str,
        metadata: Dict[str, str],
    ) -> None:
        """Multipart upload for large files."""
        # Initiate multipart upload
        mpu_params = {
            "Bucket": self._bucket_name,
            "Key": key,
            "ContentType": content_type,
            "Metadata": metadata,
            "StorageClass": self._storage_class,
        }
        
        if self._kms_key_id:
            mpu_params["ServerSideEncryption"] = "aws:kms"
            mpu_params["SSEKMSKeyId"] = self._kms_key_id
        
        mpu = self._s3_client.create_multipart_upload(**mpu_params)
        upload_id = mpu["UploadId"]
        
        try:
            # Upload parts
            parts = []
            part_number = 1
            offset = 0
            
            while offset < len(content):
                chunk = content[offset : offset + self.MULTIPART_CHUNKSIZE]
                
                response = self._s3_client.upload_part(
                    Bucket=self._bucket_name,
                    Key=key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk,
                )
                
                parts.append({"PartNumber": part_number, "ETag": response["ETag"]})
                
                part_number += 1
                offset += self.MULTIPART_CHUNKSIZE
            
            # Complete multipart upload
            self._s3_client.complete_multipart_upload(
                Bucket=self._bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            
            logger.debug(
                "Completed multipart upload for %s (%d bytes, %d parts)",
                key,
                len(content),
                len(parts),
            )
            
        except Exception as e:
            # Abort multipart upload on failure
            self._s3_client.abort_multipart_upload(
                Bucket=self._bucket_name, Key=key, UploadId=upload_id
            )
            logger.error("Aborted multipart upload for %s: %s", key, e)
            raise
    
    def _build_object_metadata(
        self, document: EvidenceDocument, object_type: str, filename: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Build S3 object metadata for chain of custody and searchability.
        
        Note: S3 metadata keys must be lowercase and values must be strings.
        """
        metadata = {
            "tenant-id": self._tenant_id,
            "document-id": document.document_id,
            "source": document.source,
            "object-type": object_type,
            "collected-at": document.collected_at.isoformat(),
            "custodian-id": document.custodian.identifier,
        }
        
        if document.custodian.email:
            metadata["custodian-email"] = document.custodian.email
        
        if document.subject:
            # Truncate subject if too long (S3 metadata limit is 2KB per header)
            subject_truncated = document.subject[:200]
            metadata["subject"] = subject_truncated
        
        if filename:
            metadata["filename"] = filename
        
        # Add hash for integrity verification
        if object_type == "body" and document.body_text:
            content_hash = hashlib.sha256(document.body_text.encode("utf-8")).hexdigest()
            metadata["content-sha256"] = content_hash
        
        return metadata


class SqliteMetadataStore(MetadataStore):
    def __init__(self, config: StorageTargetConfig) -> None:
        path = config.params.get("path")
        if not path:
            raise ValueError("SqliteMetadataStore requires path param")
        self._path = Path(path)
        if self._path.parent:
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    collected_at TEXT NOT NULL,
                    custodian_id TEXT,
                    custodian_email TEXT,
                    subject TEXT,
                    raw_path TEXT,
                    metadata_json TEXT
                )
                """
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def index(self, document: EvidenceDocument) -> None:
        self.bulk_index([document])

    def bulk_index(self, documents: List[EvidenceDocument]) -> None:
        if not documents:
            return
        with self._conn() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO documents (
                    document_id,
                    source,
                    collected_at,
                    custodian_id,
                    custodian_email,
                    subject,
                    raw_path,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        doc.document_id,
                        doc.source,
                        doc.collected_at.isoformat(),
                        doc.custodian.identifier,
                        doc.custodian.email,
                        doc.subject,
                        doc.raw_path,
                        json.dumps(doc.metadata),
                    )
                    for doc in documents
                ],
            )


class PostgresMetadataStore(MetadataStore):
    """
    Production-grade PostgreSQL metadata store with connection pooling.
    
    Features:
    - Connection pooling for performance
    - Full-text search capability
    - JSONB for flexible metadata
    - Proper indexing for fast queries
    - Audit trail (chain of custody)
    - Transaction support
    """
    
    def __init__(self, config: StorageTargetConfig) -> None:
        """
        Initialize PostgreSQL metadata store.
        
        Required params:
        - host: PostgreSQL host (default: localhost)
        - port: PostgreSQL port (default: 5432)
        - database: Database name
        - user: Database user
        - password: Database password
        
        Optional params:
        - min_connections: Minimum pool size (default: 2)
        - max_connections: Maximum pool size (default: 10)
        """
        self._validate_config(config)
        
        # Connection parameters
        self._host = config.params.get("host", "localhost")
        self._port = config.params.get("port", 5432)
        self._database = config.params["database"]
        self._user = config.params["user"]
        self._password = config.params["password"]
        
        # Connection pool settings
        min_conn = config.params.get("min_connections", 2)
        max_conn = config.params.get("max_connections", 10)
        
        # Create connection pool
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                host=self._host,
                port=self._port,
                database=self._database,
                user=self._user,
                password=self._password,
            )
            logger.info(
                "Initialized PostgreSQL connection pool: host=%s, database=%s, pool_size=%d-%d",
                self._host,
                self._database,
                min_conn,
                max_conn,
            )
        except psycopg2.Error as e:
            logger.error("Failed to create PostgreSQL connection pool: %s", e)
            raise
    
    def _validate_config(self, config: StorageTargetConfig) -> None:
        """Validate required configuration parameters."""
        required = ["database", "user", "password"]
        for param in required:
            if param not in config.params:
                raise ValueError(f"PostgresMetadataStore requires '{param}' in params")
    
    @contextmanager
    def _get_connection(self):
        """Get a connection from the pool with automatic cleanup."""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Database transaction failed: %s", e)
            raise
        finally:
            self._pool.putconn(conn)
    
    def index(self, document: EvidenceDocument) -> None:
        """Index a single document."""
        self.bulk_index([document])
    
    def bulk_index(self, documents: List[EvidenceDocument]) -> None:
        """
        Efficiently index multiple documents in a single transaction.
        
        This method:
        1. Inserts/updates custodians
        2. Inserts/updates documents
        3. Inserts attachments
        4. Records chain of custody events
        """
        if not documents:
            return
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                for doc in documents:
                    # 1. Insert/get custodian
                    custodian_id = self._upsert_custodian(cursor, doc)
                    
                    # 2. Insert/update document
                    doc_id = self._upsert_document(cursor, doc, custodian_id)
                    
                    # 3. Insert attachments
                    self._insert_attachments(cursor, doc, doc_id)
                    
                    # 4. Record chain of custody events
                    self._insert_custody_events(cursor, doc, doc_id)
                
                conn.commit()
                logger.info("Successfully indexed %d documents in PostgreSQL", len(documents))
                
            except psycopg2.Error as e:
                conn.rollback()
                logger.error("Failed to index documents: %s", e)
                raise
            finally:
                cursor.close()
    
    def _upsert_custodian(self, cursor, document: EvidenceDocument) -> int:
        """Insert or update custodian and return their ID."""
        cursor.execute(
            """
            INSERT INTO custodians (identifier, display_name, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (identifier) 
            DO UPDATE SET
                display_name = EXCLUDED.display_name,
                email = EXCLUDED.email,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                document.custodian.identifier,
                document.custodian.display_name,
                document.custodian.email,
            ),
        )
        return cursor.fetchone()[0]
    
    def _upsert_document(self, cursor, document: EvidenceDocument, custodian_id: int) -> int:
        """Insert or update document and return its ID."""
        cursor.execute(
            """
            INSERT INTO documents (
                document_id,
                source,
                custodian_id,
                subject,
                body_text,
                raw_path,
                collected_at,
                metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id)
            DO UPDATE SET
                source = EXCLUDED.source,
                custodian_id = EXCLUDED.custodian_id,
                subject = EXCLUDED.subject,
                body_text = EXCLUDED.body_text,
                raw_path = EXCLUDED.raw_path,
                collected_at = EXCLUDED.collected_at,
                metadata_json = EXCLUDED.metadata_json,
                indexed_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (
                document.document_id,
                document.source,
                custodian_id,
                document.subject,
                document.body_text,
                document.raw_path,
                document.collected_at,
                json.dumps(document.metadata),
            ),
        )
        return cursor.fetchone()[0]
    
    def _insert_attachments(self, cursor, document: EvidenceDocument, doc_id: int) -> None:
        """Insert attachments for a document."""
        if not document.attachments:
            return
        
        # Delete existing attachments for this document
        cursor.execute("DELETE FROM attachments WHERE document_id = %s", (doc_id,))
        
        # Insert new attachments
        attachment_data = [
            (
                doc_id,
                att.filename,
                att.content_type,
                att.size_bytes,
                att.checksum_sha256,
            )
            for att in document.attachments
        ]
        
        psycopg2.extras.execute_batch(
            cursor,
            """
            INSERT INTO attachments (document_id, filename, content_type, size_bytes, checksum_sha256)
            VALUES (%s, %s, %s, %s, %s)
            """,
            attachment_data,
        )
    
    def _insert_custody_events(self, cursor, document: EvidenceDocument, doc_id: int) -> None:
        """Record chain of custody events for a document."""
        if not document.chain_of_custody:
            return
        
        custody_data = [
            (
                doc_id,
                event.timestamp,
                event.actor,
                event.action,
                json.dumps(event.metadata),
            )
            for event in document.chain_of_custody
        ]
        
        psycopg2.extras.execute_batch(
            cursor,
            """
            INSERT INTO custody_events (document_id, event_timestamp, actor, action, metadata_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            custody_data,
        )
    
    def search(self, query: str, limit: int = 100) -> List[Dict]:
        """
        Full-text search across documents.
        
        Args:
            query: Search query string
            limit: Maximum number of results
        
        Returns:
            List of document dictionaries with relevance scores
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute(
                """
                SELECT 
                    d.document_id,
                    d.source,
                    d.subject,
                    d.collected_at,
                    c.identifier as custodian_identifier,
                    c.email as custodian_email,
                    ts_rank(d.search_vector, plainto_tsquery('english', %s)) as relevance
                FROM documents d
                LEFT JOIN custodians c ON d.custodian_id = c.id
                WHERE d.search_vector @@ plainto_tsquery('english', %s)
                ORDER BY relevance DESC
                LIMIT %s
                """,
                (query, query, limit),
            )
            
            results = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in results]
    
    def get_documents_by_custodian(self, custodian_email: str, limit: int = 100) -> List[Dict]:
        """Get all documents from a specific custodian."""
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute(
                """
                SELECT 
                    d.document_id,
                    d.source,
                    d.subject,
                    d.collected_at,
                    c.identifier as custodian_identifier,
                    c.email as custodian_email
                FROM documents d
                JOIN custodians c ON d.custodian_id = c.id
                WHERE c.email = %s
                ORDER BY d.collected_at DESC
                LIMIT %s
                """,
                (custodian_email, limit),
            )
            
            results = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in results]
    
    def get_document_count(self) -> int:
        """Get total number of indexed documents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM documents")
            count = cursor.fetchone()[0]
            cursor.close()
            return count
    
    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("Closed PostgreSQL connection pool")


def build_object_store(config: StorageTargetConfig) -> ObjectStore:
    store_type = config.type
    if store_type == "local_fs":
        return LocalFilesystemObjectStore(config)
    elif store_type == "s3":
        return S3ObjectStore(config)
    raise ValueError(f"Unsupported object store type: {store_type}")


def build_metadata_store(config: StorageTargetConfig) -> MetadataStore:
    store_type = config.type
    if store_type == "sqlite":
        return SqliteMetadataStore(config)
    elif store_type == "postgres":
        return PostgresMetadataStore(config)
    raise ValueError(f"Unsupported metadata store type: {store_type}")
