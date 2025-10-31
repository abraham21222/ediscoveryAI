-- Database Performance Optimization
-- Run this to add indexes and optimize queries

-- Add indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_documents_embedding_not_null 
ON documents(document_id) WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_ai_analysis_classification 
ON ai_analysis(classification) WHERE classification IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_review_classification 
ON user_review(user_classification) WHERE user_classification IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_review_reviewed 
ON user_review(is_reviewed) WHERE is_reviewed = TRUE;

CREATE INDEX IF NOT EXISTS idx_documents_collected_at_desc 
ON documents(collected_at DESC);

-- Optimize full-text search
CREATE INDEX IF NOT EXISTS idx_documents_search_gin 
ON documents USING gin(search_vector);

-- Add statistics for query planner
ANALYZE documents;
ANALYZE ai_analysis;
ANALYZE user_review;
ANALYZE user_tags;
ANALYZE custodians;

-- Create materialized view for dashboard stats (faster loading)
CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_stats AS
SELECT 
    (SELECT COUNT(*) FROM documents) as total_documents,
    (SELECT COUNT(*) FROM ai_analysis) as analyzed_documents,
    (SELECT COUNT(*) FROM documents d LEFT JOIN ai_analysis a ON d.document_id = a.document_id WHERE a.document_id IS NULL) as pending_documents,
    (SELECT COUNT(*) FROM ai_analysis WHERE classification IN ('Hot Document', 'Privileged')) as high_priority_count,
    (SELECT COUNT(DISTINCT custodian_id) FROM documents) as total_custodians,
    (SELECT COUNT(*) FROM user_review WHERE is_reviewed = TRUE) as reviewed_documents,
    (SELECT COUNT(DISTINCT tag_name) FROM user_tags) as unique_tags
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_dashboard_stats_refresh 
ON dashboard_stats ((1));

-- Function to refresh stats (call this periodically)
CREATE OR REPLACE FUNCTION refresh_dashboard_stats()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_stats;
END;
$$ LANGUAGE plpgsql;

COMMENT ON MATERIALIZED VIEW dashboard_stats IS 'Cached dashboard statistics for faster loading';
COMMENT ON FUNCTION refresh_dashboard_stats() IS 'Refresh dashboard stats (run periodically or after bulk operations)';

-- Show optimization results
SELECT 'Database optimizations applied successfully!' as status;
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public' 
ORDER BY tablename, indexname;

