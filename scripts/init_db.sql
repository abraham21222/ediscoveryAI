-- PostgreSQL schema for ediscovery metadata storage
-- This creates tables to store document metadata, custodians, and search indexes

-- Enable UUID extension for unique IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Custodians table (people who created/sent documents)
CREATE TABLE IF NOT EXISTS custodians (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(500),
    email VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_custodians_email ON custodians(email);
CREATE INDEX IF NOT EXISTS idx_custodians_identifier ON custodians(identifier);

-- Documents table (main metadata for each document)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL UNIQUE,
    source VARCHAR(100) NOT NULL,
    custodian_id INTEGER REFERENCES custodians(id),
    subject TEXT,
    body_text TEXT,
    raw_path TEXT,
    collected_at TIMESTAMP NOT NULL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_json JSONB,
    
    -- Add full-text search column
    search_vector tsvector,
    
    CONSTRAINT unique_document_id UNIQUE (document_id)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_custodian ON documents(custodian_id);
CREATE INDEX IF NOT EXISTS idx_documents_collected_at ON documents(collected_at);
CREATE INDEX IF NOT EXISTS idx_documents_document_id ON documents(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_metadata_json ON documents USING gin(metadata_json);
CREATE INDEX IF NOT EXISTS idx_documents_search ON documents USING gin(search_vector);

-- Attachments table (files attached to documents)
CREATE TABLE IF NOT EXISTS attachments (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(200),
    size_bytes BIGINT,
    checksum_sha256 VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for attachment lookups
CREATE INDEX IF NOT EXISTS idx_attachments_document_id ON attachments(document_id);
CREATE INDEX IF NOT EXISTS idx_attachments_checksum ON attachments(checksum_sha256);

-- Chain of custody events (audit trail)
CREATE TABLE IF NOT EXISTS custody_events (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    event_timestamp TIMESTAMP NOT NULL,
    actor VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for custody lookups
CREATE INDEX IF NOT EXISTS idx_custody_document_id ON custody_events(document_id);
CREATE INDEX IF NOT EXISTS idx_custody_timestamp ON custody_events(event_timestamp);

-- Matters table (legal cases/matters)
CREATE TABLE IF NOT EXISTS matters (
    id SERIAL PRIMARY KEY,
    matter_id VARCHAR(255) NOT NULL UNIQUE,
    matter_name VARCHAR(500) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_matters_matter_id ON matters(matter_id);
CREATE INDEX IF NOT EXISTS idx_matters_status ON matters(status);

-- Document-Matter relationship (many-to-many)
CREATE TABLE IF NOT EXISTS document_matters (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    matter_id INTEGER REFERENCES matters(id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (document_id, matter_id)
);

-- Function to automatically update search_vector
CREATE OR REPLACE FUNCTION documents_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := 
        setweight(to_tsvector('english', COALESCE(NEW.subject, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.body_text, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update search vector on insert/update
DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents;
CREATE TRIGGER documents_search_vector_trigger
    BEFORE INSERT OR UPDATE OF subject, body_text
    ON documents
    FOR EACH ROW
    EXECUTE FUNCTION documents_search_vector_update();

-- View for easy document querying with custodian info
CREATE OR REPLACE VIEW documents_with_custodians AS
SELECT 
    d.id,
    d.document_id,
    d.source,
    d.subject,
    d.collected_at,
    d.indexed_at,
    c.identifier as custodian_identifier,
    c.display_name as custodian_name,
    c.email as custodian_email,
    d.metadata_json,
    (SELECT COUNT(*) FROM attachments a WHERE a.document_id = d.id) as attachment_count
FROM documents d
LEFT JOIN custodians c ON d.custodian_id = c.id;

-- Grant permissions (for application user)
-- Note: You may need to create a specific user for your application
-- Example: CREATE USER ediscovery_app WITH PASSWORD 'your_secure_password';
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ediscovery_app;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ediscovery_app;

-- Insert default matter for testing
INSERT INTO matters (matter_id, matter_name, description, status)
VALUES ('default', 'Default Matter', 'Default matter for uncategorized documents', 'active')
ON CONFLICT (matter_id) DO NOTHING;

-- Summary: Database ready for ediscovery metadata storage!
-- Tables created:
--   - custodians: People who created/sent documents
--   - documents: Main document metadata
--   - attachments: Files attached to documents
--   - custody_events: Audit trail for chain of custody
--   - matters: Legal cases/matters
--   - document_matters: Link documents to matters
-- 
-- Features:
--   - Full-text search enabled (search_vector)
--   - JSONB for flexible metadata
--   - Proper indexes for fast queries
--   - Foreign keys for data integrity
--   - Audit trail for compliance

