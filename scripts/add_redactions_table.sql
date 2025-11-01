-- Create table to store document redactions
CREATE TABLE IF NOT EXISTS document_redactions (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    redaction_type VARCHAR(100) NOT NULL,  -- e.g., 'names', 'financial', 'pii'
    redaction_prompt TEXT,
    redacted_subject TEXT,
    redacted_body TEXT,
    redaction_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_redactions_document_id ON document_redactions(document_id);
CREATE INDEX IF NOT EXISTS idx_redactions_created_at ON document_redactions(created_at);
