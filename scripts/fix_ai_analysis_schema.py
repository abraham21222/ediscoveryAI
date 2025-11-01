#!/usr/bin/env python3
"""
Fix ai_analysis table schema to include all required columns.
"""

import psycopg2
import sys

def main():
    try:
        # Connect to database
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="ediscovery_metadata",
            user="abrahambloom",
            password=""
        )
        cursor = conn.cursor()
        
        print("🔍 Checking ai_analysis table schema...")
        
        # Check if table exists
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'ai_analysis'
            ORDER BY ordinal_position;
        """)
        
        existing_columns = {row[0]: row[1] for row in cursor.fetchall()}
        print(f"✅ Found ai_analysis table with {len(existing_columns)} columns:")
        for col, dtype in existing_columns.items():
            print(f"   - {col}: {dtype}")
        
        # Define required columns
        required_columns = {
            'ai_summary': 'TEXT',
            'ai_relevance': 'INTEGER',
            'ai_classification': 'VARCHAR(50)',
            'ai_topics': 'TEXT[]',
            'ai_analyzed_at': 'TIMESTAMP'
        }
        
        # Add missing columns
        print("\n🔧 Adding missing columns...")
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                print(f"   Adding column: {col_name} ({col_type})")
                cursor.execute(f"""
                    ALTER TABLE ai_analysis 
                    ADD COLUMN IF NOT EXISTS {col_name} {col_type};
                """)
                conn.commit()
                print(f"   ✅ Added {col_name}")
            else:
                print(f"   ✓ {col_name} already exists")
        
        print("\n✅ Schema fix complete!")
        
        # Verify final schema
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'ai_analysis'
            ORDER BY ordinal_position;
        """)
        
        print("\n📊 Final schema:")
        for row in cursor.fetchall():
            print(f"   - {row[0]}: {row[1]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

