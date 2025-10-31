#!/usr/bin/env python3
"""
E-Discovery Search Tool

Command-line interface for searching and querying documents in PostgreSQL.

Examples:
    # Simple text search
    python3 scripts/search.py "quarterly report"
    
    # Search by custodian
    python3 scripts/search.py --custodian user5@example.com
    
    # Search with date range
    python3 scripts/search.py "contract" --from 2025-01-01 --to 2025-12-31
    
    # Export to CSV
    python3 scripts/search.py "falcon" --export csv --output results.csv
    
    # Show statistics
    python3 scripts/search.py --stats
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


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
    # Try to get from environment or use defaults
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


def search_documents(
    query: Optional[str] = None,
    custodian: Optional[str] = None,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100
) -> List[Dict]:
    """Search documents with various filters."""
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Build query dynamically
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
    
    # Add relevance score if doing text search
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
    
    # Add text search filter
    if query:
        sql_parts.append("AND d.search_vector @@ plainto_tsquery('english', %s)")
        params.append(query)
        params.append(query)  # Used twice (once for rank, once for filter)
    
    # Add custodian filter
    if custodian:
        sql_parts.append("AND c.email ILIKE %s")
        params.append(f"%{custodian}%")
    
    # Add source filter
    if source:
        sql_parts.append("AND d.source = %s")
        params.append(source)
    
    # Add date filters
    if date_from:
        sql_parts.append("AND d.collected_at >= %s")
        params.append(date_from)
    
    if date_to:
        sql_parts.append("AND d.collected_at <= %s")
        params.append(date_to)
    
    # Add ordering and limit
    if query:
        sql_parts.append("ORDER BY relevance DESC, d.collected_at DESC")
    else:
        sql_parts.append("ORDER BY d.collected_at DESC")
    
    sql_parts.append(f"LIMIT {limit}")
    
    # Execute query
    sql = " ".join(sql_parts)
    cursor.execute(sql, params)
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return [dict(row) for row in results]


def get_statistics() -> Dict:
    """Get database statistics."""
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
    
    # Top custodians
    cursor.execute("""
        SELECT c.email, c.display_name, COUNT(*) as doc_count
        FROM documents d
        JOIN custodians c ON d.custodian_id = c.id
        GROUP BY c.email, c.display_name
        ORDER BY doc_count DESC
        LIMIT 10
    """)
    stats["top_custodians"] = [dict(row) for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    
    return stats


def print_results(results: List[Dict], show_body: bool = False):
    """Print search results in a nice format."""
    if not results:
        print("\n❌ No results found.\n")
        return
    
    print(f"\n✅ Found {len(results)} document(s)\n")
    print("=" * 100)
    
    for i, doc in enumerate(results, 1):
        print(f"\n#{i} | {doc['document_id']}")
        print(f"Subject:    {doc['subject']}")
        print(f"From:       {doc['custodian_name']} <{doc['custodian_email']}>")
        print(f"Date:       {doc['collected_at']}")
        print(f"Source:     {doc['source']}")
        
        if 'relevance' in doc:
            print(f"Relevance:  {doc['relevance']:.4f}")
        
        if show_body and doc.get('body_text'):
            body_preview = doc['body_text'][:200]
            if len(doc['body_text']) > 200:
                body_preview += "..."
            print(f"Body:       {body_preview}")
        
        print("-" * 100)
    
    print()


def export_results(results: List[Dict], format: str, output: str):
    """Export results to file."""
    if format == "csv":
        with open(output, 'w', newline='') as f:
            if not results:
                return
            
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        
        print(f"✅ Exported {len(results)} results to {output}")
    
    elif format == "json":
        # Convert datetime objects to strings
        for doc in results:
            for key, value in doc.items():
                if isinstance(value, datetime):
                    doc[key] = value.isoformat()
        
        with open(output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"✅ Exported {len(results)} results to {output}")


def print_statistics(stats: Dict):
    """Print database statistics."""
    print("\n" + "=" * 60)
    print("📊 E-DISCOVERY DATABASE STATISTICS")
    print("=" * 60)
    
    print(f"\n📄 Total Documents:  {stats['total_documents']:,}")
    print(f"👥 Total Custodians: {stats['total_custodians']:,}")
    
    if stats['date_range']['earliest']:
        print(f"\n📅 Date Range:")
        print(f"   Earliest: {stats['date_range']['earliest']}")
        print(f"   Latest:   {stats['date_range']['latest']}")
    
    if stats['by_source']:
        print(f"\n📂 Documents by Source:")
        for source_stat in stats['by_source']:
            print(f"   {source_stat['source']:30} {source_stat['count']:>6,} docs")
    
    if stats['top_custodians']:
        print(f"\n🏆 Top Custodians:")
        for i, cust in enumerate(stats['top_custodians'], 1):
            name = cust['display_name'] or cust['email']
            print(f"   {i:2}. {name:30} {cust['doc_count']:>6,} docs")
    
    print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Search e-discovery documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "quarterly report"                    Search for text
  %(prog)s --custodian user5@example.com         Find docs by custodian
  %(prog)s "contract" --from 2025-01-01          Search with date filter
  %(prog)s "falcon" --export csv -o results.csv  Export to CSV
  %(prog)s --stats                               Show statistics
        """
    )
    
    # Search options
    parser.add_argument("query", nargs="?", help="Search query text")
    parser.add_argument("--custodian", "-c", help="Filter by custodian email")
    parser.add_argument("--source", "-s", help="Filter by source")
    parser.add_argument("--from", dest="date_from", help="Filter from date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="Filter to date (YYYY-MM-DD)")
    parser.add_argument("--limit", "-l", type=int, default=100, help="Max results (default: 100)")
    
    # Display options
    parser.add_argument("--body", "-b", action="store_true", help="Show body text preview")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    
    # Export options
    parser.add_argument("--export", "-e", choices=["csv", "json"], help="Export format")
    parser.add_argument("--output", "-o", help="Export output file")
    
    args = parser.parse_args()
    
    # Load environment
    load_env()
    
    try:
        # Show statistics
        if args.stats:
            stats = get_statistics()
            print_statistics(stats)
            return
        
        # Search documents
        results = search_documents(
            query=args.query,
            custodian=args.custodian,
            source=args.source,
            date_from=args.date_from,
            date_to=args.date_to,
            limit=args.limit
        )
        
        # Export if requested
        if args.export and args.output:
            export_results(results, args.export, args.output)
        else:
            # Print results
            print_results(results, show_body=args.body)
    
    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

