-- Database migration: Add file analysis and multimodal support
-- Run this to add file type tracking and corruption detection to your database

-- 1. Add file analysis columns to attachments table
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS file_category VARCHAR(50);
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS data_quality VARCHAR(50);
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS quality_details TEXT;
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS md5_hash VARCHAR(32);
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS detected_mime VARCHAR(255);
ALTER TABLE attachments ADD COLUMN IF NOT EXISTS is_processable BOOLEAN DEFAULT TRUE;

-- 2. Add indexes for filtering by file type and quality
CREATE INDEX IF NOT EXISTS idx_attachments_file_category ON attachments(file_category);
CREATE INDEX IF NOT EXISTS idx_attachments_data_quality ON attachments(data_quality);
CREATE INDEX IF NOT EXISTS idx_attachments_processable ON attachments(is_processable);
CREATE INDEX IF NOT EXISTS idx_attachments_md5 ON attachments(md5_hash);

-- 3. Add document-level file analysis (for documents that are standalone files, not emails)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_category VARCHAR(50);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS data_quality VARCHAR(50);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS quality_details TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS detected_mime VARCHAR(255);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_extension VARCHAR(20);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT;

-- 4. Add indexes for document filtering
CREATE INDEX IF NOT EXISTS idx_documents_file_category ON documents(file_category);
CREATE INDEX IF NOT EXISTS idx_documents_data_quality ON documents(data_quality);
CREATE INDEX IF NOT EXISTS idx_documents_file_extension ON documents(file_extension);

-- 5. Create a view for easy querying of corrupted/problematic files
CREATE OR REPLACE VIEW problematic_files AS
SELECT 
    d.document_id,
    d.source,
    d.subject,
    d.file_category,
    d.data_quality,
    d.quality_details,
    d.file_extension,
    d.file_size_bytes,
    d.collected_at,
    c.email as custodian_email
FROM documents d
LEFT JOIN custodians c ON d.custodian_id = c.id
WHERE d.data_quality != 'valid' OR d.data_quality IS NULL;

-- 6. Create a view for attachment quality summary
CREATE OR REPLACE VIEW attachment_quality_summary AS
SELECT 
    d.document_id,
    d.subject,
    a.filename,
    a.file_category,
    a.data_quality,
    a.quality_details,
    a.size_bytes,
    a.content_type,
    a.detected_mime
FROM documents d
JOIN attachments a ON d.id = a.document_id
WHERE a.data_quality != 'valid' OR a.is_processable = FALSE;

-- 7. Create statistics view for file types
CREATE OR REPLACE VIEW file_type_statistics AS
SELECT 
    file_category,
    data_quality,
    COUNT(*) as count,
    SUM(file_size_bytes) as total_size_bytes,
    AVG(file_size_bytes) as avg_size_bytes
FROM documents
WHERE file_category IS NOT NULL
GROUP BY file_category, data_quality
ORDER BY file_category, data_quality;

-- 8. Create function to get document count by file type
CREATE OR REPLACE FUNCTION get_file_type_counts()
RETURNS TABLE(file_category TEXT, total BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(d.file_category, 'unknown')::TEXT as file_category,
        COUNT(*)::BIGINT as total
    FROM documents d
    GROUP BY d.file_category
    ORDER BY total DESC;
END;
$$ LANGUAGE plpgsql;

-- 9. Create function to get corruption status counts
CREATE OR REPLACE FUNCTION get_quality_status_counts()
RETURNS TABLE(data_quality TEXT, total BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(d.data_quality, 'unknown')::TEXT as data_quality,
        COUNT(*)::BIGINT as total
    FROM documents d
    GROUP BY d.data_quality
    ORDER BY total DESC;
END;
$$ LANGUAGE plpgsql;

-- 10. Add comments for documentation
COMMENT ON COLUMN attachments.file_category IS 'File category: document, image, video, audio, spreadsheet, etc.';
COMMENT ON COLUMN attachments.data_quality IS 'Quality status: valid, corrupted, encrypted, truncated, invalid_format, suspicious';
COMMENT ON COLUMN attachments.quality_details IS 'Detailed description of quality issues';
COMMENT ON COLUMN attachments.md5_hash IS 'MD5 hash for deduplication';
COMMENT ON COLUMN attachments.detected_mime IS 'MIME type detected from file magic bytes';
COMMENT ON COLUMN attachments.is_processable IS 'Whether file can be processed (extracted, previewed, etc.)';

COMMENT ON COLUMN documents.file_category IS 'Document file category';
COMMENT ON COLUMN documents.data_quality IS 'Document quality status';
COMMENT ON COLUMN documents.file_extension IS 'File extension (.pdf, .docx, etc.)';
COMMENT ON COLUMN documents.file_size_bytes IS 'File size in bytes';

-- Example queries:

-- Find all corrupted files:
-- SELECT * FROM problematic_files WHERE data_quality = 'corrupted';

-- Find all encrypted documents:
-- SELECT * FROM documents WHERE data_quality = 'encrypted';

-- Get statistics by file type:
-- SELECT * FROM file_type_statistics;

-- Count documents by type:
-- SELECT * FROM get_file_type_counts();

-- Count by quality status:
-- SELECT * FROM get_quality_status_counts();

-- Find all images:
-- SELECT * FROM documents WHERE file_category = 'image';

-- Find large video files:
-- SELECT * FROM documents 
-- WHERE file_category = 'video' AND file_size_bytes > 100000000
-- ORDER BY file_size_bytes DESC;

-- Find suspicious files:
-- SELECT * FROM documents WHERE data_quality = 'suspicious';

