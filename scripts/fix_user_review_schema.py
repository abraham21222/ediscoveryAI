#!/usr/bin/env python3
"""
Fix user_review table schema.
"""

import psycopg2

def main():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="ediscovery_metadata",
        user="abrahambloom",
        password=""
    )
    cursor = conn.cursor()
    
    print("🔧 Fixing user_review table...")
    
    # Add review_status column if missing
    cursor.execute("""
        ALTER TABLE user_review 
        ADD COLUMN IF NOT EXISTS review_status VARCHAR(50);
    """)
    
    conn.commit()
    print("✅ Added review_status column")
    
    cursor.close()
    conn.close()
    print("✅ Schema fix complete!")

if __name__ == "__main__":
    main()

