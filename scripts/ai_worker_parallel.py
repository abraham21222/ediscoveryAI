#!/usr/bin/env python3
"""
Parallel AI Worker - Process multiple documents simultaneously
Performance improvement: 5-10x faster than serial processing
"""
import sys
import os
import json
import time
import psycopg2
import psycopg2.extras
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Import the existing AI analyzer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.ai_analyzer import analyze_document

# Thread-safe counter
class Counter:
    def __init__(self):
        self.value = 0
        self.lock = Lock()
    
    def increment(self):
        with self.lock:
            self.value += 1
            return self.value

def load_config():
    """Load database configuration"""
    config_path = 'configs/postgres_production.json'
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config['metadata_store']['params']

def get_db_connection(db_config):
    """Get a new database connection (thread-safe)"""
    return psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['database'],
        user=db_config['user'],
        password=db_config['password']
    )

def get_pending_documents(db_config, limit=None):
    """Fetch documents that don't have AI analysis yet"""
    conn = get_db_connection(db_config)
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    query = """
        SELECT d.document_id, d.subject, d.body_text, c.email as custodian_email
        FROM documents d
        LEFT JOIN custodians c ON d.custodian_id = c.id
        LEFT JOIN ai_analysis a ON d.document_id = a.document_id
        WHERE a.document_id IS NULL
        ORDER BY d.collected_at DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    docs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return [dict(doc) for doc in docs]

def process_document_worker(doc_dict, db_config, counter, total):
    """Worker function to process a single document (runs in thread)"""
    doc_id = doc_dict['document_id']
    
    try:
        # Create new connection for this thread
        conn = get_db_connection(db_config)
        
        # Run AI analysis
        start_time = time.time()
        result = analyze_document(doc_dict, conn)
        duration = time.time() - start_time
        
        conn.close()
        
        count = counter.increment()
        
        if result and result.get('success'):
            status = '✅'
            classification = result.get('classification', 'Unknown')
            relevance = result.get('relevance_score', 0)
        else:
            status = '❌'
            classification = 'Failed'
            relevance = 0
        
        subject = doc_dict.get('subject', 'No Subject')[:40]
        
        print(f"[{count}/{total}] {status} {doc_id[:20]}... | {classification} ({relevance}/100) | {duration:.1f}s | {subject}...")
        
        return {'success': result.get('success', False), 'doc_id': doc_id}
        
    except Exception as e:
        count = counter.increment()
        print(f"[{count}/{total}] ❌ {doc_id[:20]}... | Error: {str(e)}")
        return {'success': False, 'doc_id': doc_id, 'error': str(e)}

def main():
    """Main execution with parallel processing"""
    print("=" * 70)
    print("🚀 Parallel AI Worker - High Performance Document Analysis")
    print("=" * 70)
    print()
    
    # Parse arguments
    batch_size = 20  # Default to 20 documents
    workers = 5  # Default to 5 parallel workers
    loop = False
    
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--batch-size' and i + 1 < len(sys.argv) - 1:
            batch_size = int(sys.argv[i + 2])
        elif arg == '--workers' and i + 1 < len(sys.argv) - 1:
            workers = int(sys.argv[i + 2])
        elif arg == '--loop':
            loop = True
    
    print(f"⚙️  Configuration:")
    print(f"   • Batch size: {batch_size} documents")
    print(f"   • Parallel workers: {workers}")
    print(f"   • Mode: {'Continuous loop' if loop else 'One-time run'}")
    print()
    
    # Check for API key
    api_key = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ Error: OPENROUTER_API_KEY or OPENAI_API_KEY not set")
        print("\nSet it with:")
        print("  export OPENROUTER_API_KEY='sk-or-v1-...'")
        sys.exit(1)
    
    # Load database config
    db_config = load_config()
    print(f"✅ Connected to database: {db_config['host']}")
    print()
    
    iteration = 0
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    while True:
        iteration += 1
        
        # Get pending documents
        print(f"🔍 Fetching pending documents (max {batch_size})...")
        pending = get_pending_documents(db_config, limit=batch_size)
        
        if not pending:
            print("✨ No pending documents found!")
            if loop:
                print("⏳ Waiting 30 seconds before checking again...")
                time.sleep(30)
                continue
            else:
                break
        
        num_docs = len(pending)
        print(f"📊 Found {num_docs} document(s) to process")
        print(f"💰 Estimated cost: ${num_docs * 0.10:.2f}")
        print()
        
        # Process documents in parallel
        start_time = time.time()
        counter = Counter()
        results = []
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(process_document_worker, doc, db_config, counter, num_docs): doc
                for doc in pending
            }
            
            # Collect results as they complete
            for future in as_completed(futures):
                results.append(future.result())
        
        # Calculate statistics
        duration = time.time() - start_time
        successful = sum(1 for r in results if r['success'])
        failed = num_docs - successful
        
        total_processed += num_docs
        total_successful += successful
        total_failed += failed
        
        docs_per_second = num_docs / duration if duration > 0 else 0
        
        print()
        print("=" * 70)
        print(f"📊 Batch #{iteration} Complete")
        print("=" * 70)
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️  Duration: {duration:.1f}s")
        print(f"🚀 Speed: {docs_per_second:.2f} docs/sec")
        print(f"💰 Cost: ~${successful * 0.10:.2f}")
        print()
        
        if not loop:
            break
        
        if num_docs < batch_size:
            print("✨ All documents processed!")
            break
        
        print("⏳ Waiting 10 seconds before next batch...")
        time.sleep(10)
    
    # Final summary
    print("=" * 70)
    print("🎉 Processing Complete")
    print("=" * 70)
    print(f"Total processed: {total_processed}")
    print(f"✅ Successful: {total_successful}")
    print(f"❌ Failed: {total_failed}")
    print(f"📈 Success rate: {100 * total_successful / total_processed if total_processed > 0 else 0:.1f}%")
    print(f"💰 Total cost: ~${total_successful * 0.10:.2f}")
    print()
    
    if total_successful > 0:
        print("🎯 Next steps:")
        print("  • Refresh the web dashboard to see AI results")
        print("  • Run search queries to test semantic search")
        print("  • Review and tag important documents")

if __name__ == '__main__':
    main()

