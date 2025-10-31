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
    limit = int(data.get('limit', 50))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query
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
                c.display_name as custodian_name
        """]
        
        if query:
            sql_parts[0] += """,
                ts_rank(d.search_vector, plainto_tsquery('english', %s)) as relevance
            """
        
        sql_parts.append("""
            FROM documents d
            LEFT JOIN custodians c ON d.custodian_id = c.id
            WHERE 1=1
        """)
        
        params = []
        
        if query:
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
        
        if query:
            sql_parts.append("ORDER BY relevance DESC, d.collected_at DESC")
        else:
            sql_parts.append("ORDER BY d.collected_at DESC")
        
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
        return jsonify({
            'success': False,
            'error': str(e)
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
                c.display_name as custodian_name
            FROM documents d
            LEFT JOIN custodians c ON d.custodian_id = c.id
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
            SELECT event_timestamp, actor, action, metadata_json
            FROM custody_events ce
            JOIN documents d ON ce.document_id = d.id
            WHERE d.document_id = %s
            ORDER BY event_timestamp
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


if __name__ == '__main__':
    load_env()
    print("\n" + "=" * 60)
    print("🌐 E-Discovery Web Dashboard")
    print("=" * 60)
    print("\nStarting server...")
    print("Open in browser: http://localhost:8080")
    print("\nPress Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=8080)

