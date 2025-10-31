#!/usr/bin/env python3
"""
AI Worker - Continuous Document Analysis

This worker runs continuously and processes pending documents in batches.
It monitors the database for new documents and automatically analyzes them with AI.

Usage:
    python3 scripts/ai_worker.py                    # Run forever
    python3 scripts/ai_worker.py --once             # Process one batch and exit
    python3 scripts/ai_worker.py --batch-size 5     # Custom batch size
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the analyzer functions
from ai_analyzer import (
    load_env,
    get_db_connection,
    analyze_document_with_ai,
    store_ai_analysis
)
import psycopg2
import psycopg2.extras


def get_pending_documents(batch_size=10):
    """Get documents that haven't been analyzed yet."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    cursor.execute("""
        SELECT d.document_id, d.subject, d.body_text, c.email as custodian_email
        FROM documents d
        LEFT JOIN custodians c ON d.custodian_id = c.id
        LEFT JOIN ai_analysis a ON d.document_id = a.document_id
        WHERE a.id IS NULL
        ORDER BY d.collected_at DESC
        LIMIT %s
    """, (batch_size,))
    
    documents = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return documents


def process_batch(batch_size=10):
    """Process one batch of pending documents."""
    documents = get_pending_documents(batch_size)
    
    if not documents:
        return 0
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing {len(documents)} pending documents...")
    
    success_count = 0
    for i, doc in enumerate(documents, 1):
        try:
            print(f"  [{i}/{len(documents)}] Analyzing: {doc['document_id']}")
            
            # Analyze with AI
            analysis = analyze_document_with_ai(
                subject=doc['subject'] or "",
                body=doc['body_text'] or "",
                custodian=doc['custodian_email'] or "Unknown"
            )
            
            # Store results
            store_ai_analysis(doc['document_id'], analysis)
            
            success_count += 1
            print(f"      ✓ {analysis.get('classification')} | Relevance: {analysis.get('relevance_score')}/100")
            
        except Exception as e:
            print(f"      ✗ Error: {str(e)[:100]}")
            continue
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Batch complete: {success_count}/{len(documents)} successful\n")
    return success_count


def run_worker(batch_size=10, sleep_interval=30, run_once=False):
    """Run the worker continuously."""
    
    print("=" * 70)
    print("🤖 AI WORKER STARTED")
    print("=" * 70)
    print(f"Batch size: {batch_size}")
    print(f"Sleep interval: {sleep_interval}s")
    print(f"Mode: {'One-time' if run_once else 'Continuous'}")
    print("=" * 70)
    print()
    
    if run_once:
        # Run once and exit
        processed = process_batch(batch_size)
        print(f"✅ Processed {processed} documents. Exiting.")
        return
    
    # Run continuously
    try:
        while True:
            try:
                processed = process_batch(batch_size)
                
                if processed == 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No pending documents. Waiting {sleep_interval}s...")
                
                time.sleep(sleep_interval)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Worker error: {e}")
                print(f"Retrying in {sleep_interval}s...")
                time.sleep(sleep_interval)
    
    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("🛑 AI WORKER STOPPED")
        print("=" * 70)


def get_worker_status():
    """Get current worker status and pending count."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get pending count
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM documents d
        LEFT JOIN ai_analysis a ON d.document_id = a.document_id
        WHERE a.id IS NULL
    """)
    pending = cursor.fetchone()['count']
    
    # Get total analyzed
    cursor.execute("SELECT COUNT(*) as count FROM ai_analysis")
    analyzed = cursor.fetchone()['count']
    
    # Get recent analysis
    cursor.execute("""
        SELECT analyzed_at
        FROM ai_analysis
        ORDER BY analyzed_at DESC
        LIMIT 1
    """)
    last_analysis = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("📊 AI WORKER STATUS")
    print("=" * 70)
    print(f"Pending documents:   {pending}")
    print(f"Analyzed documents:  {analyzed}")
    if last_analysis and last_analysis['analyzed_at']:
        print(f"Last analysis:       {last_analysis['analyzed_at']}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="AI Worker for continuous document analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    parser.add_argument("--batch-size", type=int, default=10, help="Documents per batch (default: 10)")
    parser.add_argument("--sleep", type=int, default=30, help="Sleep interval in seconds (default: 30)")
    parser.add_argument("--status", action="store_true", help="Show worker status and exit")
    
    args = parser.parse_args()
    
    load_env()
    
    # Check if OpenRouter API key is set
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("\n❌ Error: OPENROUTER_API_KEY not found in environment")
        print("Please set it in your .env file\n")
        sys.exit(1)
    
    try:
        if args.status:
            get_worker_status()
        else:
            run_worker(
                batch_size=args.batch_size,
                sleep_interval=args.sleep,
                run_once=args.once
            )
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

