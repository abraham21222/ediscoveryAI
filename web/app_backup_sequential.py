#!/usr/bin/env python3
"""
E-Discovery Web Dashboard

A simple Flask web application for searching and reviewing documents.

Run with:
    python3 web/app.py
    
Then open: http://localhost:5000
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import psycopg2
import psycopg2.extras

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'


def load_env():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def get_db_connection():
    """Get PostgreSQL database connection."""
    host = os.environ.get("POSTGRES_HOST", "ediscovery-metadata-db.cm526e4m45t7.us-east-1.rds.amazonaws.com")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    database = os.environ.get("POSTGRES_DATABASE", "ediscovery_metadata")
    user = os.environ.get("POSTGRES_USER", "ediscovery")
    password = os.environ.get("POSTGRES_PASSWORD", "BfXUdqKbo7pTAuks")
    
    return psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )


@app.route('/')
def index():
    """Home page with search interface."""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def api_search():
    """API endpoint for searching documents."""
    data = request.get_json()
    
    query = data.get('query', '').strip()
    custodian = data.get('custodian', '').strip()
    date_from = data.get('date_from', '').strip()
    date_to = data.get('date_to', '').strip()
    classification = data.get('classification', '').strip()
    min_relevance = data.get('min_relevance', '')
    file_category = data.get('file_category', '').strip()  # NEW: file type filter
    data_quality = data.get('data_quality', '').strip()    # NEW: corruption filter
    limit = int(data.get('limit', 50))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query with AI analysis
        sql_parts = ["""
            SELECT 
                d.document_id,
                d.source,
                d.subject,
                d.body_text,
                d.collected_at,
                d.indexed_at,
                c.identifier as custodian_id,
                c.email as custodian_email,
                c.display_name as custodian_name,
                a.summary as ai_summary,
                a.relevance_score as ai_relevance,
                a.classification as ai_classification,
                a.privilege_risk as ai_privilege_risk,
                a.topics as ai_topics,
                a.analyzed_at as ai_analyzed_at,
                ur.user_classification,
                ur.user_relevance_score,
                ur.is_reviewed,
                ARRAY_AGG(DISTINCT ut.tag_name) FILTER (WHERE ut.tag_name IS NOT NULL) as user_tags
        """]
        
        # Use semantic search if query provided and embeddings exist
        use_semantic = False
        query_embedding = None
        
        if query:
            # Check if embeddings are available
            try:
                cursor.execute("SELECT COUNT(*) as count FROM documents WHERE embedding IS NOT NULL")
                embeddings_count = cursor.fetchone()['count']
                
                if embeddings_count > 0:
                    use_semantic = True
                    # Generate embedding for search query
                    try:
                        from openai import OpenAI
                        import os
                        
                        api_key = os.getenv('OPENAI_API_KEY') or os.getenv('OPENROUTER_API_KEY')
                        if api_key:
                            if api_key.startswith('sk-or-'):
                                client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
                            else:
                                client = OpenAI(api_key=api_key)
                            
                            response = client.embeddings.create(
                                input=query,
                                model="text-embedding-3-small"
                            )
                            query_embedding = response.data[0].embedding
                    except Exception as e:
                        print(f"Warning: Failed to generate query embedding: {e}")
                        use_semantic = False
            except Exception as e:
                # Embedding column doesn't exist, skip semantic search
                conn.rollback()  # Roll back the failed transaction
                use_semantic = False
                embeddings_count = 0
        
        if use_semantic and query_embedding:
            # Semantic search using vector similarity
            sql_parts[0] += """,
                (1 - (d.embedding <=> %s::vector)) as relevance
            """
        elif query:
            # Fall back to keyword search
            sql_parts[0] += """,
                ts_rank(d.search_vector, plainto_tsquery('english', %s)) as relevance
            """
        
        sql_parts.append("""
            FROM documents d
            LEFT JOIN custodians c ON d.custodian_id = c.id
            LEFT JOIN ai_analysis a ON d.document_id = a.document_id
            LEFT JOIN user_review ur ON d.document_id = ur.document_id
            LEFT JOIN user_tags ut ON d.document_id = ut.document_id
            WHERE 1=1
        """)
        
        params = []
        
        if use_semantic and query_embedding:
            # Use vector similarity
            params.append(query_embedding)
        elif query:
            # Use keyword search
            sql_parts.append("AND d.search_vector @@ plainto_tsquery('english', %s)")
            params.append(query)
            params.append(query)
        
        if custodian:
            sql_parts.append("AND c.email ILIKE %s")
            params.append(f"%{custodian}%")
        
        if date_from:
            sql_parts.append("AND d.collected_at >= %s")
            params.append(date_from)
        
        if date_to:
            sql_parts.append("AND d.collected_at <= %s")
            params.append(date_to)
        
        # AI filters
        if classification:
            sql_parts.append("AND a.classification = %s")
            params.append(classification)
        
        if min_relevance:
            sql_parts.append("AND a.relevance_score >= %s")
            params.append(int(min_relevance))
        
        # File type filter (NEW)
        if file_category:
            sql_parts.append("AND d.file_category = %s")
            params.append(file_category)
        
        # Data quality filter (NEW)
        if data_quality:
            sql_parts.append("AND d.data_quality = %s")
            params.append(data_quality)
        
        # Group by all non-aggregated columns (for ARRAY_AGG)
        group_by_cols = """d.document_id, d.source, d.subject, d.body_text, d.collected_at, d.indexed_at,
                     c.identifier, c.email, c.display_name,
                     a.summary, a.relevance_score, a.classification, a.privilege_risk, a.topics, a.analyzed_at,
                     ur.user_classification, ur.user_relevance_score, ur.is_reviewed"""
        
        if query:
            # Add relevance column to GROUP BY if it was added to SELECT
            group_by_cols += ", relevance"
        
        sql_parts.append(f"GROUP BY {group_by_cols}")
        
        # Ordering - prioritize user-tagged documents, then AI relevance
        if query:
            sql_parts.append("ORDER BY relevance DESC, COALESCE(a.relevance_score, 0) DESC, d.collected_at DESC")
        else:
            sql_parts.append("ORDER BY COALESCE(ur.user_relevance_score, a.relevance_score, 0) DESC, d.collected_at DESC")
        
        sql_parts.append(f"LIMIT {limit}")
        
        sql = " ".join(sql_parts)
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        # Convert to JSON-serializable format
        documents = []
        for row in results:
            doc = dict(row)
            if isinstance(doc.get('collected_at'), datetime):
                doc['collected_at'] = doc['collected_at'].isoformat()
            if isinstance(doc.get('indexed_at'), datetime):
                doc['indexed_at'] = doc['indexed_at'].isoformat()
            documents.append(doc)
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(documents),
            'documents': documents
        })
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"=== Search API Error ===")
        print(error_detail)
        print(f"========================")
        return jsonify({
            'success': False,
            'error': str(e),
            'detail': error_detail[:500]  # Truncate for response
        }), 500


@app.route('/api/stats', methods=['GET'])
def api_stats():
    """API endpoint for database statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        stats = {}
        
        # Total documents
        cursor.execute("SELECT COUNT(*) as count FROM documents")
        stats["total_documents"] = cursor.fetchone()["count"]
        
        # Total custodians
        cursor.execute("SELECT COUNT(DISTINCT custodian_id) as count FROM documents")
        stats["total_custodians"] = cursor.fetchone()["count"]
        
        # Documents by source
        cursor.execute("""
            SELECT source, COUNT(*) as count 
            FROM documents 
            GROUP BY source 
            ORDER BY count DESC
        """)
        stats["by_source"] = [dict(row) for row in cursor.fetchall()]
        
        # Date range
        cursor.execute("""
            SELECT 
                MIN(collected_at) as earliest,
                MAX(collected_at) as latest
            FROM documents
        """)
        dates = cursor.fetchone()
        stats["date_range"] = {
            "earliest": dates["earliest"].isoformat() if dates["earliest"] else None,
            "latest": dates["latest"].isoformat() if dates["latest"] else None
        }
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ai-stats', methods=['GET'])
def api_ai_stats():
    """API endpoint for AI analysis statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        stats = {}
        
        # Total documents and analyzed
        cursor.execute("""
            SELECT 
                COUNT(d.id) as total_docs,
                COUNT(a.id) as analyzed_docs
            FROM documents d
            LEFT JOIN ai_analysis a ON d.document_id = a.document_id
        """)
        counts = cursor.fetchone()
        stats["total_documents"] = counts["total_docs"]
        stats["analyzed_documents"] = counts["analyzed_docs"]
        stats["pending_documents"] = counts["total_docs"] - counts["analyzed_docs"]
        
        # By classification
        cursor.execute("""
            SELECT classification, COUNT(*) as count
            FROM ai_analysis
            GROUP BY classification
            ORDER BY count DESC
        """)
        stats["by_classification"] = [dict(row) for row in cursor.fetchall()]
        
        # High priority docs
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM ai_analysis
            WHERE relevance_score >= 70
        """)
        stats["high_priority_count"] = cursor.fetchone()["count"]
        
        # Privilege risk
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM ai_analysis
            WHERE privilege_risk >= 50
        """)
        stats["privilege_risk_count"] = cursor.fetchone()["count"]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/document/<document_id>', methods=['GET'])
def api_document(document_id):
    """API endpoint to get full document details."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT 
                d.*,
                c.identifier as custodian_id,
                c.email as custodian_email,
                c.display_name as custodian_name,
                a.summary as ai_summary,
                a.entities as ai_entities,
                a.relevance_score as ai_relevance,
                a.classification as ai_classification,
                a.privilege_risk as ai_privilege_risk,
                a.topics as ai_topics,
                a.action_items as ai_action_items,
                a.review_notes as ai_review_notes,
                a.analyzed_at as ai_analyzed_at
            FROM documents d
            LEFT JOIN custodians c ON d.custodian_id = c.id
            LEFT JOIN ai_analysis a ON d.document_id = a.document_id
            WHERE d.document_id = %s
        """, (document_id,))
        
        result = cursor.fetchone()
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'Document not found'
            }), 404
        
        doc = dict(result)
        if isinstance(doc.get('collected_at'), datetime):
            doc['collected_at'] = doc['collected_at'].isoformat()
        if isinstance(doc.get('indexed_at'), datetime):
            doc['indexed_at'] = doc['indexed_at'].isoformat()
        
        # Get chain of custody
        cursor.execute("""
            SELECT ce.event_timestamp, ce.actor, ce.action, ce.metadata_json
            FROM custody_events ce
            JOIN documents d ON ce.document_id = d.id
            WHERE d.document_id = %s
            ORDER BY ce.event_timestamp
        """, (document_id,))
        
        custody_events = []
        for row in cursor.fetchall():
            event = dict(row)
            if isinstance(event.get('event_timestamp'), datetime):
                event['event_timestamp'] = event['event_timestamp'].isoformat()
            custody_events.append(event)
        
        doc['chain_of_custody'] = custody_events
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'document': doc
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================
# USER-DRIVEN FEATURES API
# ============================================================

@app.route('/api/document/<document_id>/tags', methods=['GET', 'POST', 'DELETE'])
def api_document_tags(document_id):
    """Manage user tags for a document."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if request.method == 'GET':
            # Get all tags for document
            cursor.execute("""
                SELECT tag_name, created_at 
                FROM user_tags 
                WHERE document_id = %s
                ORDER BY created_at
            """, (document_id,))
            tags = [dict(row) for row in cursor.fetchall()]
            
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'tags': tags})
        
        elif request.method == 'POST':
            # Add new tag
            data = request.get_json()
            tag_name = data.get('tag_name', '').strip()
            
            if not tag_name:
                return jsonify({'success': False, 'error': 'Tag name required'}), 400
            
            cursor.execute("""
                INSERT INTO user_tags (document_id, tag_name)
                VALUES (%s, %s)
                ON CONFLICT (document_id, tag_name) DO NOTHING
                RETURNING id
            """, (document_id, tag_name))
            
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Tag added'})
        
        elif request.method == 'DELETE':
            # Remove tag
            data = request.get_json()
            tag_name = data.get('tag_name', '').strip()
            
            cursor.execute("""
                DELETE FROM user_tags 
                WHERE document_id = %s AND tag_name = %s
            """, (document_id, tag_name))
            
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Tag removed'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/document/<document_id>/review', methods=['GET', 'POST'])
def api_document_review(document_id):
    """Manage user review for a document."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if request.method == 'GET':
            # Get review status
            cursor.execute("""
                SELECT user_classification, user_relevance_score, 
                       is_reviewed, review_notes, reviewed_at
                FROM user_review 
                WHERE document_id = %s
            """, (document_id,))
            review = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if review:
                return jsonify({'success': True, 'review': dict(review)})
            else:
                return jsonify({'success': True, 'review': None})
        
        elif request.method == 'POST':
            # Update review
            data = request.get_json()
            
            cursor.execute("""
                INSERT INTO user_review 
                    (document_id, user_classification, user_relevance_score, 
                     is_reviewed, review_notes)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE SET
                    user_classification = EXCLUDED.user_classification,
                    user_relevance_score = EXCLUDED.user_relevance_score,
                    is_reviewed = EXCLUDED.is_reviewed,
                    review_notes = EXCLUDED.review_notes,
                    reviewed_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                document_id,
                data.get('user_classification'),
                data.get('user_relevance_score'),
                data.get('is_reviewed', False),
                data.get('review_notes')
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Review saved'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tags/all', methods=['GET'])
def api_all_tags():
    """Get all unique tags used across documents."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cursor.execute("""
            SELECT tag_name, COUNT(*) as count
            FROM user_tags
            GROUP BY tag_name
            ORDER BY count DESC, tag_name
        """)
        
        tags = [dict(row) for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'tags': tags})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Global progress tracker for custom AI analysis
custom_ai_progress = {}

@app.route('/api/custom-ai-analysis', methods=['POST'])
def api_custom_ai_analysis():
    """Run custom AI analysis on selected documents."""
    import sys
    print("="*60, file=sys.stderr)
    print("CUSTOM AI ANALYSIS ENDPOINT HIT", file=sys.stderr)
    print("="*60, file=sys.stderr)
    sys.stderr.flush()
    
    try:
        data = request.get_json()
        document_ids = data.get('document_ids', [])
        custom_prompt = data.get('custom_prompt', '')
        create_tags = data.get('create_tags', True)  # Default to True
        redaction_mode = data.get('redaction_mode', False)
        redaction_prompt = data.get('redaction_prompt', '')
        print(f"Documents: {document_ids}", file=sys.stderr)
        print(f"Prompt: {custom_prompt[:50]}", file=sys.stderr)
        print(f"Create Tags: {create_tags}", file=sys.stderr)
        print(f"Redaction Mode: {redaction_mode}", file=sys.stderr)
        sys.stderr.flush()
        
        if not document_ids:
            return jsonify({'success': False, 'error': 'No documents provided'}), 400
        
        if not custom_prompt:
            return jsonify({'success': False, 'error': 'No prompt provided'}), 400
        
        if redaction_mode and not redaction_prompt:
            return jsonify({'success': False, 'error': 'Redaction mode requires redaction instructions'}), 400
        
        # Create a job ID
        import time
        import hashlib
        job_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]
        
        # Initialize progress tracking
        custom_ai_progress[job_id] = {
            'total': len(document_ids),
            'processed': 0,
            'completed': False,
            'started_at': time.time(),
            'current_document': None,
            'current_subject': None,
            'results': [],  # Store results for summary
            'redactions': [],  # Store redacted documents
            'create_tags': create_tags,
            'redaction_mode': redaction_mode
        }
        
        # Process immediately (synchronous for now - threading has issues with Flask debug mode)
        import sys
        print(f">>> Starting immediate processing for job {job_id}", file=sys.stderr)
        sys.stderr.flush()
        
        # Call the processing function directly
        process_custom_ai_analysis(job_id, document_ids, custom_prompt, create_tags, redaction_mode, redaction_prompt)
        
        print(f">>> Processing complete for job {job_id}", file=sys.stderr)
        sys.stderr.flush()
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'total_documents': len(document_ids),
            'estimated_cost': len(document_ids) * 0.10
        })
    
    except Exception as e:
        print(f"Error starting custom AI analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/custom-ai-progress/<job_id>', methods=['GET'])
def api_custom_ai_progress(job_id):
    """Get progress of custom AI analysis job."""
    try:
        if job_id not in custom_ai_progress:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        progress = custom_ai_progress[job_id]
        return jsonify({
            'success': True,
            'processed': progress['processed'],
            'total': progress['total'],
            'completed': progress['completed'],
            'current_document': progress.get('current_document'),
            'current_subject': progress.get('current_subject'),
            'results': progress.get('results', []) if progress['completed'] else [],
            'redactions': progress.get('redactions', []) if progress['completed'] else [],
            'redaction_mode': progress.get('redaction_mode', False)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def process_custom_ai_analysis(job_id, document_ids, custom_prompt, create_tags=True, redaction_mode=False, redaction_prompt=''):
    """Process documents with custom AI prompt using PARALLEL PROCESSING with Grok 4 Fast."""
    import os
    import sys
    from openai import OpenAI
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    
    print(f"=== Starting PARALLEL custom AI analysis job {job_id} ===", file=sys.stderr)
    print(f"Documents to process: {len(document_ids)} documents", file=sys.stderr)
    print(f"Model: x-ai/grok-4-fast (FAST MODE)", file=sys.stderr)
    print(f"Custom prompt: {custom_prompt[:100]}...", file=sys.stderr)
    sys.stderr.flush()
    
    try:
        # Initialize OpenAI client
        api_key = os.environ.get('OPENROUTER_API_KEY')
        if not api_key:
            print("Error: OPENROUTER_API_KEY not set", file=sys.stderr)
            custom_ai_progress[job_id]['completed'] = True
            return
        
        print(f"API key found: {api_key[:20]}...", file=sys.stderr)
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        
        # Thread-safe lock for database writes and progress updates
        db_lock = threading.Lock()
        
        def analyze_single_document(doc_id):
            try:
                # Update progress with current document
                custom_ai_progress[job_id]['current_document'] = doc_id
                
                # Get document content
                cursor.execute("""
                    SELECT d.document_id, d.subject, d.body_text
                    FROM documents d
                    WHERE d.document_id = %s
                """, (doc_id,))
                
                doc = cursor.fetchone()
                if not doc:
                    continue
                
                # Update progress with subject
                custom_ai_progress[job_id]['current_subject'] = doc['subject']
                
                # Prepare content for AI
                content = f"Subject: {doc['subject']}\n\nBody:\n{doc['body_text'] or 'No content'}"
                
                # Call AI with enhanced prompt for structured output
                structured_prompt = f"""{custom_prompt}

Please provide your analysis in this format:
RELEVANCE: [score 0-100]
PRIVILEGE_RISK: [score 0-100, likelihood this is attorney-client privileged communication]
CLASSIFICATION: [relevant/not-relevant/needs-review]
KEY FINDINGS: [bullet points of key findings]
ANALYSIS: [your detailed analysis]"""
                
                response = client.chat.completions.create(
                    model="x-ai/grok-4-fast",  # UPGRADED TO GROK 4 FAST!
                    messages=[
                        {
                            "role": "system",
                            "content": structured_prompt
                        },
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    max_tokens=700,
                    temperature=0.3
                )
                
                ai_response = response.choices[0].message.content
                
                # Parse the structured response
                import re
                relevance_match = re.search(r'RELEVANCE:\s*(\d+)', ai_response, re.IGNORECASE)
                relevance_score = int(relevance_match.group(1)) if relevance_match else 50
                
                privilege_match = re.search(r'PRIVILEGE[_\s]*RISK:\s*(\d+)', ai_response, re.IGNORECASE)
                privilege_risk = int(privilege_match.group(1)) if privilege_match else 0
                
                classification_match = re.search(r'CLASSIFICATION:\s*(\S+)', ai_response, re.IGNORECASE)
                classification = classification_match.group(1) if classification_match else 'needs-review'
                
                findings_match = re.search(r'KEY FINDINGS:\s*(.+?)(?=ANALYSIS:|$)', ai_response, re.IGNORECASE | re.DOTALL)
                key_findings = findings_match.group(1).strip() if findings_match else ''
                
                # Extract topics/tags from the analysis
                topics = []
                if 'fraud' in ai_response.lower() or 'fraud' in custom_prompt.lower():
                    topics.append('Financial Fraud')
                if 'privilege' in ai_response.lower() or 'attorney' in ai_response.lower():
                    topics.append('Attorney-Client')
                if 'compliance' in ai_response.lower() or 'regulatory' in ai_response.lower():
                    topics.append('Compliance')
                
                # Save to ai_analysis table (main AI fields)
                cursor.execute("""
                    INSERT INTO ai_analysis (
                        document_id, ai_summary, ai_relevance, ai_classification,
                        ai_topics, ai_analyzed_at, privilege_risk
                    ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
                    ON CONFLICT (document_id)
                    DO UPDATE SET
                        ai_summary = EXCLUDED.ai_summary,
                        ai_relevance = EXCLUDED.ai_relevance,
                        ai_classification = EXCLUDED.ai_classification,
                        ai_topics = EXCLUDED.ai_topics,
                        ai_analyzed_at = CURRENT_TIMESTAMP,
                        privilege_risk = EXCLUDED.privilege_risk
                """, (
                    doc_id,
                    key_findings[:500] if key_findings else ai_response[:500],
                    relevance_score,
                    classification,
                    topics[:3] if topics else None,
                    privilege_risk
                ))
                
                # Also store full analysis in user_review notes
                cursor.execute("""
                    INSERT INTO user_review (document_id, review_notes, review_status)
                    VALUES (%s, %s, 'reviewed')
                    ON CONFLICT (document_id)
                    DO UPDATE SET
                        review_notes = CASE
                            WHEN user_review.review_notes IS NULL THEN EXCLUDED.review_notes
                            ELSE user_review.review_notes || E'\n\n--- Custom AI Analysis ---\n' || EXCLUDED.review_notes
                        END,
                        reviewed_at = CURRENT_TIMESTAMP
                """, (doc_id, f"Custom Analysis:\n{ai_response}"))
                
                conn.commit()
                
                # Create tags if requested
                if create_tags:
                    tags_to_create = []
                    
                    # Add classification-based tags
                    if classification == 'relevant':
                        tags_to_create.append('AI: Relevant')
                    elif classification == 'not-relevant':
                        tags_to_create.append('AI: Not Relevant')
                    else:
                        tags_to_create.append('AI: Needs Review')
                    
                    # Add relevance-based tags
                    if relevance_score >= 70:
                        tags_to_create.append('High Priority')
                    elif relevance_score >= 40:
                        tags_to_create.append('Medium Priority')
                    else:
                        tags_to_create.append('Low Priority')
                    
                    # Add topic-based tags
                    for topic in topics:
                        tags_to_create.append(topic)
                    
                    # Create the tags in database
                    for tag_name in tags_to_create:
                        try:
                            cursor.execute("""
                                INSERT INTO user_tags (document_id, tag_name)
                                VALUES (%s, %s)
                                ON CONFLICT (document_id, tag_name) DO NOTHING
                            """, (doc_id, tag_name))
                        except Exception as tag_error:
                            print(f"Warning: Could not create tag '{tag_name}': {tag_error}", file=sys.stderr)
                    
                    conn.commit()
                    print(f"Created {len(tags_to_create)} tags for {doc_id}: {tags_to_create}", file=sys.stderr)
                    sys.stderr.flush()
                
                # Perform redaction if requested
                redacted_subject = None
                redacted_body = None
                redaction_details = None
                
                if redaction_mode and redaction_prompt:
                    print(f"🔒 Performing redaction for {doc_id}...", file=sys.stderr)
                    sys.stderr.flush()
                    
                    # Call AI to identify and redact content
                    redaction_system_prompt = f"""{redaction_prompt}

Please identify ALL content that matches the redaction criteria and provide:
1. A list of what needs to be redacted with specific instances
2. The redacted subject line (if applicable)
3. The redacted body text with replacements like [REDACTED - SSN], [REDACTED - NAME], etc.

Format your response as:
REDACTION_SUMMARY: [brief summary of what was redacted]
REDACTED_SUBJECT: [redacted subject line]
REDACTED_BODY: [full body text with redactions applied]"""
                    
                    redaction_content = f"SUBJECT: {doc['subject']}\n\nBODY:\n{doc['body_text']}"
                    
                    redaction_response = client.chat.completions.create(
                        model="openai/gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": redaction_system_prompt},
                            {"role": "user", "content": redaction_content}
                        ],
                        max_tokens=1500,
                        temperature=0.1
                    )
                    
                    redaction_result = redaction_response.choices[0].message.content
                    
                    # Parse redaction results
                    summary_match = re.search(r'REDACTION_SUMMARY:\s*(.+?)(?=REDACTED_SUBJECT:|$)', redaction_result, re.IGNORECASE | re.DOTALL)
                    redaction_details = summary_match.group(1).strip() if summary_match else "Redactions applied"
                    
                    subject_match = re.search(r'REDACTED_SUBJECT:\s*(.+?)(?=REDACTED_BODY:|$)', redaction_result, re.IGNORECASE | re.DOTALL)
                    redacted_subject = subject_match.group(1).strip() if subject_match else doc['subject']
                    
                    body_match = re.search(r'REDACTED_BODY:\s*(.+?)$', redaction_result, re.IGNORECASE | re.DOTALL)
                    redacted_body = body_match.group(1).strip() if body_match else doc['body_text']
                    
                    # Store redacted version in results
                    custom_ai_progress[job_id]['redactions'].append({
                        'document_id': doc_id,
                        'original_subject': doc['subject'],
                        'original_body': doc['body_text'],
                        'redacted_subject': redacted_subject,
                        'redacted_body': redacted_body,
                        'redaction_summary': redaction_details
                    })
                    
                    print(f"✅ Redaction complete for {doc_id}: {redaction_details}", file=sys.stderr)
                    sys.stderr.flush()
                
                # Store result for summary
                result_data = {
                    'document_id': doc_id,
                    'subject': doc['subject'],
                    'relevance': relevance_score,
                    'privilege_risk': privilege_risk,
                    'classification': classification,
                    'key_findings': key_findings[:200] if key_findings else ai_response[:200]
                }
                
                if redaction_mode:
                    result_data['redacted'] = True
                    result_data['redaction_summary'] = redaction_details
                
                custom_ai_progress[job_id]['results'].append(result_data)
                
                # Update progress
                custom_ai_progress[job_id]['processed'] += 1
                
            except Exception as e:
                print(f"!!! Error processing document {doc_id}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
                continue
        
        cursor.close()
        conn.close()
        
        # Mark as completed
        custom_ai_progress[job_id]['completed'] = True
        print(f"Custom AI analysis job {job_id} completed: {custom_ai_progress[job_id]['processed']}/{custom_ai_progress[job_id]['total']}")
        
    except Exception as e:
        print(f"=== ERROR in custom AI processing thread ===")
        print(f"Job ID: {job_id}")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        print(f"===========================================")
        custom_ai_progress[job_id]['completed'] = True


@app.route('/relativity')
def relativity_integration():
    """Relativity integration page."""
    return render_template('relativity.html')


@app.route('/api/relativity/upload', methods=['POST'])
def api_relativity_upload():
    """Upload and parse a Relativity .DAT file."""
    try:
        # Check if file was uploaded
        if 'datFile' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'})
        
        file = request.files['datFile']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'})
        
        # Save uploaded file
        upload_dir = Path('uploads/relativity')
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        dat_path = upload_dir / file.filename
        file.save(str(dat_path))
        
        # Parse the DAT file
        from integrations.relativity_loader import RelativityLoadFileParser
        
        parser = RelativityLoadFileParser(dat_path)
        documents = parser.parse()
        
        # Convert to JSON-serializable format
        doc_list = []
        for doc in documents[:100]:  # Limit to first 100 for preview
            doc_list.append({
                'doc_id': doc.doc_id,
                'bates_number': doc.bates_number,
                'custodian': doc.custodian,
                'date_sent': doc.date_sent,
                'subject': doc.subject,
                'from_field': doc.from_field,
                'to_field': doc.to_field,
            })
        
        # Store parsed documents in session/temp storage
        import json
        parsed_file = upload_dir / f"{file.filename}.parsed.json"
        with open(parsed_file, 'w') as f:
            json.dump([doc.metadata for doc in documents], f)
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'total_documents': len(documents),
            'fields': parser.get_field_names(),
            'preview': doc_list
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/relativity/analyze', methods=['POST'])
def api_relativity_analyze():
    """Run AI analysis on parsed documents."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'success': False, 'error': 'No filename provided'})
        
        # Load parsed documents
        upload_dir = Path('uploads/relativity')
        dat_path = upload_dir / filename
        
        if not dat_path.exists():
            return jsonify({'success': False, 'error': 'File not found'})
        
        # Parse and analyze
        from integrations.relativity_loader import (
            RelativityLoadFileParser,
            RelativityEnrichmentExporter
        )
        from test_relativity_integration import simulate_ai_analysis
        
        parser = RelativityLoadFileParser(dat_path)
        documents = parser.parse()
        
        # Run AI analysis
        analyzed_docs = []
        for doc in documents:
            analyzed_doc = simulate_ai_analysis(doc)
            analyzed_docs.append(analyzed_doc)
        
        # Export enrichment file
        enrichment_file = upload_dir / f"{filename}.enrichment.csv"
        exporter = RelativityEnrichmentExporter(enrichment_file)
        exporter.export(analyzed_docs)
        
        # Calculate statistics
        responsive_yes = sum(1 for d in analyzed_docs if d.ai_responsive == 'Yes')
        responsive_no = sum(1 for d in analyzed_docs if d.ai_responsive == 'No')
        responsive_maybe = sum(1 for d in analyzed_docs if d.ai_responsive == 'Maybe')
        privileged_yes = sum(1 for d in analyzed_docs if d.ai_privileged == 'Yes')
        hot_docs = sum(1 for d in analyzed_docs if d.hot_score and d.hot_score > 80)
        
        # Sample results
        sample_results = []
        for doc in analyzed_docs[:20]:
            sample_results.append({
                'doc_id': doc.doc_id,
                'subject': doc.subject,
                'ai_responsive': doc.ai_responsive,
                'ai_responsive_confidence': doc.ai_responsive_confidence,
                'ai_privileged': doc.ai_privileged,
                'ai_privilege_confidence': doc.ai_privilege_confidence,
                'ai_classification': doc.ai_classification,
                'hot_score': doc.hot_score,
                'ai_topics': doc.ai_topics,
            })
        
        return jsonify({
            'success': True,
            'enrichment_file': f"{filename}.enrichment.csv",
            'total_documents': len(analyzed_docs),
            'statistics': {
                'responsive_yes': responsive_yes,
                'responsive_no': responsive_no,
                'responsive_maybe': responsive_maybe,
                'privileged_yes': privileged_yes,
                'hot_documents': hot_docs,
            },
            'sample_results': sample_results
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/relativity/download/<filename>')
def api_relativity_download(filename):
    """Download the AI enrichment CSV file."""
    try:
        from flask import send_file
        
        upload_dir = Path('uploads/relativity')
        file_path = upload_dir / filename
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        return send_file(
            str(file_path),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    load_env()
    print("\n" + "=" * 60)
    print("🌐 E-Discovery Web Dashboard")
    print("=" * 60)
    print("\nStarting server...")
    print("Open in browser: http://localhost:8080")
    print("\nPress Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=8080)
