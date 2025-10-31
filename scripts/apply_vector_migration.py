#!/usr/bin/env python3
"""
Apply vector support migration to PostgreSQL database
"""
import sys
import os
import json
import psycopg2

def load_config():
    """Load database configuration"""
    config_path = 'configs/postgres_production.json'
    if not os.path.exists(config_path):
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    return config['metadata_store']['params']

def apply_migration(db_config):
    """Apply the vector support migration"""
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            user=db_config['user'],
            password=db_config['password']
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("🔌 Connected to database")
        
        # Read migration SQL
        with open('scripts/add_vector_support.sql', 'r') as f:
            sql = f.read()
        
        # Execute migration
        print("📝 Applying vector support migration...")
        cursor.execute(sql)
        
        print("✅ Migration applied successfully!")
        print("\nVerifying...")
        
        # Verify pgvector extension
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        result = cursor.fetchone()
        if result:
            print(f"✓ pgvector extension version: {result[0]}")
        else:
            print("⚠️  pgvector extension not found")
        
        # Verify embedding column
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'documents' AND column_name = 'embedding'
        """)
        result = cursor.fetchone()
        if result:
            print(f"✓ Embedding column added: {result[0]} ({result[1]})")
        else:
            print("⚠️  Embedding column not found")
        
        cursor.close()
        conn.close()
        
        print("\n🎉 Database is ready for semantic search!")
        
    except Exception as e:
        print(f"❌ Error applying migration: {e}")
        sys.exit(1)

if __name__ == '__main__':
    print("=" * 60)
    print("🗄️  Applying Vector Support Migration")
    print("=" * 60)
    
    db_config = load_config()
    apply_migration(db_config)

