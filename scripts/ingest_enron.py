#!/usr/bin/env python3
"""
Properly ingest Enron email dataset using the ingestion pipeline.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.config import AppConfig
from ingestion.pipeline import IngestionPipeline


def main():
    print("\n" + "=" * 60)
    print("📧 ENRON EMAIL INGESTION")
    print("=" * 60)
    
    # Load configuration
    config_path = Path("configs/enron_test.json")
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return
    
    print(f"\n📋 Loading configuration: {config_path}")
    
    # Parse configuration using AppConfig
    app_config = AppConfig.from_json(config_path)
    
    print(f"✅ Configuration loaded:")
    print(f"   Object Store: {app_config.object_store.type}")
    print(f"   Metadata Store: {app_config.metadata_store.type}")
    print(f"   Connectors: {len(app_config.connectors)}")
    for conn in app_config.connectors:
        print(f"     • {conn.name} ({conn.type})")
    
    # Initialize pipeline
    print(f"\n🔧 Initializing ingestion pipeline...")
    pipeline = IngestionPipeline(app_config)
    
    # Run ingestion
    print(f"\n🚀 Starting ingestion...")
    print("=" * 60)
    
    results = pipeline.run()
    
    print("=" * 60)
    print("\n✅ INGESTION COMPLETE!")
    print("=" * 60)
    
    # Summary
    print(f"\n📊 Summary:")
    total_docs = sum(r.processed_documents for r in results)
    print(f"   Total documents ingested: {total_docs}")
    
    for result in results:
        print(f"   • {result.connector_name}: {result.processed_documents} documents")
    
    # Show sample documents
    print(f"\n📄 Verifying in database...")
    from ingestion.storage import build_metadata_store
    from ingestion.config import StorageTargetConfig
    
    metadata_store_config = StorageTargetConfig(
        type=app_config.metadata_store.type,
        params=app_config.metadata_store.params
    )
    
    metadata_store = build_metadata_store(metadata_store_config)
    
    # Search for Enron documents
    enron_docs = metadata_store.search(
        query_text="",
        filters={"source": "enron-emails"},
        limit=100
    )
    
    print(f"✅ Found {len(enron_docs)} Enron documents in database")
    
    if enron_docs:
        print(f"\n👥 Custodians:")
        custodians = {}
        for doc in enron_docs:
            cust_id = doc.get('custodian_id', 'unknown')
            cust_name = doc.get('custodian_name', 'Unknown')
            cust_email = doc.get('custodian_email', '')
            
            key = f"{cust_name} ({cust_email})"
            if key not in custodians:
                custodians[key] = 0
            custodians[key] += 1
        
        for cust, count in sorted(custodians.items(), key=lambda x: x[1], reverse=True):
            print(f"   • {cust}: {count} emails")
        
        print(f"\n📧 Sample emails:")
        for i, doc in enumerate(enron_docs[:3], 1):
            print(f"   {i}. [{doc.get('custodian_name', 'Unknown')}] {doc.get('subject', 'No Subject')[:60]}")
    
    print(f"\n🌐 View in dashboard: http://localhost:8080")
    print(f"   Search for 'enron' or custodian names\n")


if __name__ == '__main__':
    main()
