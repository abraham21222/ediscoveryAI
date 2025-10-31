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
        print(f"Documents: {document_ids}", file=sys.stderr)
        print(f"Prompt: {custom_prompt[:50]}", file=sys.stderr)
        sys.stderr.flush()
        
        if not document_ids:
            return jsonify({'success': False, 'error': 'No documents provided'}), 400
        
        if not custom_prompt:
            return jsonify({'success': False, 'error': 'No prompt provided'}), 400
        
        # Create a job ID
        import time
        import hashlib
        job_id = hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]
        
        # Initialize progress tracking
        custom_ai_progress[job_id] = {
            'total': len(document_ids),
            'processed': 0,
            'completed': False,
            'started_at': time.time()
        }
        
        # Process immediately (synchronous for now - threading has issues with Flask debug mode)
        import sys
        print(f">>> Starting immediate processing for job {job_id}", file=sys.stderr)
        sys.stderr.flush()
        
        # Call the processing function directly
        process_custom_ai_analysis(job_id, document_ids, custom_prompt)
        
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
            'completed': progress['completed']
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def process_custom_ai_analysis(job_id, document_ids, custom_prompt):
    """Process documents with custom AI prompt (runs in background thread)."""
    import os
    import sys
    from openai import OpenAI
    
    print(f"=== Starting custom AI analysis job {job_id} ===", file=sys.stderr)
    print(f"Documents to process: {document_ids}", file=sys.stderr)
    print(f"Custom prompt: {custom_prompt[:100]}...", file=sys.stderr)
    sys.stderr.flush()
    
    try:
        # Initialize OpenAI client
        api_key = os.environ.get('OPENROUTER_API_KEY')
        if not api_key:
            print("Error: OPENROUTER_API_KEY not set")
            custom_ai_progress[job_id]['completed'] = True
            return
        
        print(f"API key found: {api_key[:20]}...")
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        for doc_id in document_ids:
            try:
                # Get document content
                cursor.execute("""
                    SELECT d.document_id, d.subject, d.body_text
                    FROM documents d
                    WHERE d.document_id = %s
                """, (doc_id,))
                
                doc = cursor.fetchone()
                if not doc:
                    continue
                
                # Prepare content for AI
                content = f"Subject: {doc['subject']}\n\nBody:\n{doc['body_text'] or 'No content'}"
                
                # Call AI with custom prompt
                response = client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": custom_prompt
                        },
                        {
                            "role": "user",
                            "content": content
                        }
                    ],
                    max_tokens=500,
                    temperature=0.3
                )
                
                ai_response = response.choices[0].message.content
                
                # Store the custom analysis in user_review notes
                cursor.execute("""
                    INSERT INTO user_review (document_id, review_notes)
                    VALUES (%s, %s)
                    ON CONFLICT (document_id)
                    DO UPDATE SET
                        review_notes = CASE
                            WHEN user_review.review_notes IS NULL THEN EXCLUDED.review_notes
                            ELSE user_review.review_notes || E'\n\n--- Custom AI Analysis ---\n' || EXCLUDED.review_notes
                        END,
                        reviewed_at = CURRENT_TIMESTAMP
                """, (doc_id, f"Custom Analysis:\n{ai_response}"))
                
                conn.commit()
                
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


if __name__ == '__main__':
    load_env()
    print("\n" + "=" * 60)
    print("🌐 E-Discovery Web Dashboard")
    print("=" * 60)
    print("\nStarting server...")
    print("Open in browser: http://localhost:8080")
    print("\nPress Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=8080, debug=True)



if __name__ == '__main__':
    load_env()
    print("\n" + "=" * 60)
    print("🌐 E-Discovery Web Dashboard")
    print("=" * 60)
    print("\nStarting server...")
    print("Open in browser: http://localhost:8080")
    print("\nPress Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=8080)
