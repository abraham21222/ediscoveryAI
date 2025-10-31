-- Add user-driven features: custom tags, user relevance, review status

-- User tags table (users can apply custom tags to documents)
CREATE TABLE IF NOT EXISTS user_tags (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    tag_name VARCHAR(100) NOT NULL,
    created_by VARCHAR(255) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, tag_name)
);

CREATE INDEX IF NOT EXISTS idx_user_tags_document ON user_tags(document_id);
CREATE INDEX IF NOT EXISTS idx_user_tags_name ON user_tags(tag_name);

-- User review status (users can mark documents as reviewed, relevant, etc.)
CREATE TABLE IF NOT EXISTS user_review (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL UNIQUE REFERENCES documents(document_id) ON DELETE CASCADE,
    user_classification VARCHAR(50), -- User's own classification (Hot, Relevant, Not Relevant, etc.)
    user_relevance_score INTEGER CHECK (user_relevance_score >= 0 AND user_relevance_score <= 100),
    is_reviewed BOOLEAN DEFAULT FALSE,
    review_notes TEXT,
    reviewed_by VARCHAR(255) DEFAULT 'user',
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_review_document ON user_review(document_id);
CREATE INDEX IF NOT EXISTS idx_user_review_classification ON user_review(user_classification);
CREATE INDEX IF NOT EXISTS idx_user_review_reviewed ON user_review(is_reviewed);

-- Saved searches/filters (users can save their custom filter combinations)
CREATE TABLE IF NOT EXISTS saved_searches (
    id SERIAL PRIMARY KEY,
    search_name VARCHAR(200) NOT NULL,
    search_query TEXT,
    filters JSONB, -- Store filter criteria as JSON
    created_by VARCHAR(255) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saved_searches_name ON saved_searches(search_name);

COMMENT ON TABLE user_tags IS 'User-defined tags for documents';
COMMENT ON TABLE user_review IS 'User review status and custom classifications';
COMMENT ON TABLE saved_searches IS 'Saved search queries and filter combinations';

