#!/usr/bin/env python3
"""
Generate vector embeddings for documents to enable semantic search
Uses OpenAI's text-embedding-3-small model (1536 dimensions)
Cost: ~$0.0001 per document
"""
import sys
import os
import json
import time
import psycopg2
import psycopg2.extras
from openai import OpenAI

def load_config():
    """Load database configuration"""
    config_path = 'configs/postgres_production.json'
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config['metadata_store']['params']

def get_openai_client():
    """Initialize OpenAI client"""
    api_key = os.getenv('OPENAI_API_KEY') or os.getenv('OPENROUTER_API_KEY')
    
    if not api_key:
        print("❌ Error: OPENAI_API_KEY or OPENROUTER_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export OPENAI_API_KEY='sk-...'")
        print("  or")
        print("  export OPENROUTER_API_KEY='sk-or-v1-...'")
        sys.exit(1)
    
    # Check if using OpenRouter
    if api_key.startswith('sk-or-'):
        return OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
    else:
        return OpenAI(api_key=api_key)

def get_documents_without_embeddings(cursor, limit=None):
    """Fetch documents that don't have embeddings yet"""
    query = """
        SELECT d.document_id, d.subject, d.body_text, c.email as custodian_email, d.collected_at
        FROM documents d
        LEFT JOIN custodians c ON d.custodian_id = c.id
        WHERE d.embedding IS NULL
        ORDER BY d.collected_at DESC
    """
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    return cursor.fetchall()

def generate_embedding(client, text, model="text-embedding-3-small"):
    """Generate embedding for a piece of text"""
    try:
        # Truncate text if too long (max ~8000 tokens for embedding models)
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars]
        
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"  ⚠️  Error generating embedding: {e}")
        return None

def update_document_embedding(cursor, document_id, embedding, model):
    """Store embedding in database"""
    try:
        cursor.execute("""
            UPDATE documents 
            SET embedding = %s::vector,
                embedding_model = %s,
                embedding_generated_at = CURRENT_TIMESTAMP
            WHERE document_id = %s
        """, (embedding, model, document_id))
        return True
    except Exception as e:
        print(f"  ⚠️  Error storing embedding: {e}")
        return False

def main():
    """Main execution"""
    print("=" * 60)
    print("🧠 Generating Vector Embeddings for Semantic Search")
    print("=" * 60)
    
    # Parse args
    batch_size = 10
    if len(sys.argv) > 1:
        try:
            batch_size = int(sys.argv[1])
        except:
            print(f"Usage: {sys.argv[0]} [batch_size]")
            sys.exit(1)
    
    # Load config
    db_config = load_config()
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
        conn.autocommit = False
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        print(f"✅ Connected to database: {db_config['host']}")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Get OpenAI client
    client = get_openai_client()
    print("✅ Connected to OpenAI API")
    
    # Get documents without embeddings
    print(f"\n🔍 Finding documents without embeddings (batch size: {batch_size})...")
    documents = get_documents_without_embeddings(cursor, limit=batch_size)
    
    if not documents:
        print("✨ All documents already have embeddings!")
        cursor.close()
        conn.close()
        return
    
    total_docs = len(documents)
    print(f"📊 Found {total_docs} documents to process")
    print(f"💰 Estimated cost: ${total_docs * 0.0001:.4f}")
    print()
    
    # Process each document
    successful = 0
    failed = 0
    
    for i, doc in enumerate(documents, 1):
        doc_id = doc['document_id']
        subject = doc['subject'] or 'No Subject'
        body = doc['body_text'] or ''
        custodian = doc['custodian_email'] or ''
        
        # Create text to embed (combine subject and body)
        text_to_embed = f"Subject: {subject}\n\nFrom: {custodian}\n\n{body}"
        
        print(f"[{i}/{total_docs}] Processing: {doc_id[:20]}...")
        print(f"  Subject: {subject[:50]}...")
        
        # Generate embedding
        embedding = generate_embedding(client, text_to_embed)
        
        if embedding:
            # Store in database
            if update_document_embedding(cursor, doc_id, embedding, "text-embedding-3-small"):
                conn.commit()
                successful += 1
                print(f"  ✅ Embedding generated and stored")
            else:
                conn.rollback()
                failed += 1
        else:
            failed += 1
        
        # Rate limiting (OpenAI has limits)
        if i < total_docs:
            time.sleep(0.2)  # Small delay between requests
        
        print()
    
    cursor.close()
    conn.close()
    
    # Summary
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"✅ Successful: {successful}")
    print(f"❌ Failed: {failed}")
    print(f"💰 Actual cost: ~${successful * 0.0001:.4f}")
    print()
    
    if successful > 0:
        print("🎉 Semantic search is now available!")
        print("\nYou can now use semantic search to find documents by meaning:")
        print("  'find contracts' → matches 'agreement', 'MOU', 'terms'")
        print("  'find complaints' → matches 'grievance', 'dispute', 'issue'")

if __name__ == '__main__':
    main()

