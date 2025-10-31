#!/usr/bin/env python3
"""
AI Document Analyzer for E-Discovery

Uses OpenRouter API (Claude, GPT-4, etc.) to:
- Summarize documents
- Extract key entities (people, companies, dates)
- Classify relevance and privilege
- Flag "hot documents"
- Generate review notes

Usage:
    python3 scripts/ai_analyzer.py --analyze-all
    python3 scripts/ai_analyzer.py --document mock-email-0
    python3 scripts/ai_analyzer.py --batch 10
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2
import psycopg2.extras
import requests

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


def analyze_document_with_ai(subject: str, body: str, custodian: str) -> Dict:
    """Analyze a document using AI (OpenRouter API)."""
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment")
    
    # Prepare the prompt
    prompt = f"""Analyze this email for e-discovery purposes. Provide a structured analysis.

Subject: {subject}
From: {custodian}
Body: {body[:2000]}  # First 2000 chars

Please provide:
1. **Summary** (2-3 sentences)
2. **Key Entities** (people, companies, dates, amounts)
3. **Relevance Score** (0-100): How relevant is this to potential litigation?
4. **Classification** (Hot Document / Relevant / Routine / Privileged)
5. **Privilege Risk** (0-100): Likelihood of attorney-client privilege
6. **Key Topics** (3-5 topics)
7. **Action Items** (if any)
8. **Review Notes** (What should an attorney focus on?)

Format your response as JSON with these exact keys:
{{
  "summary": "...",
  "entities": {{
    "people": ["name1", "name2"],
    "companies": ["company1"],
    "dates": ["2025-01-01"],
    "amounts": ["$1,000,000"]
  }},
  "relevance_score": 85,
  "classification": "Relevant",
  "privilege_risk": 15,
  "topics": ["topic1", "topic2"],
  "action_items": ["item1"],
  "review_notes": "Focus on..."
}}"""
    
    # Call OpenRouter API
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,  # Lower temperature for more consistent output
            "max_tokens": 1000
        }
    )
    
    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")
    
    result = response.json()
    ai_response = result["choices"][0]["message"]["content"]
    
    # Parse JSON from response
    try:
        # Try to extract JSON from markdown code blocks
        if "```json" in ai_response:
            json_str = ai_response.split("```json")[1].split("```")[0].strip()
        elif "```" in ai_response:
            json_str = ai_response.split("```")[1].split("```")[0].strip()
        else:
            json_str = ai_response.strip()
        
        analysis = json.loads(json_str)
        return analysis
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse AI response as JSON: {e}")
        print(f"Response: {ai_response[:500]}")
        # Return a basic analysis
        return {
            "summary": ai_response[:200],
            "entities": {"people": [], "companies": [], "dates": [], "amounts": []},
            "relevance_score": 50,
            "classification": "Needs Review",
            "privilege_risk": 0,
            "topics": [],
            "action_items": [],
            "review_notes": "AI analysis failed - manual review required"
        }


def store_ai_analysis(document_id: str, analysis: Dict):
    """Store AI analysis results in PostgreSQL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, check if ai_analysis table exists, if not create it
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_analysis (
                id SERIAL PRIMARY KEY,
                document_id VARCHAR(255) NOT NULL UNIQUE,
                summary TEXT,
                entities JSONB,
                relevance_score INTEGER,
                classification VARCHAR(50),
                privilege_risk INTEGER,
                topics JSONB,
                action_items JSONB,
                review_notes TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_document
                    FOREIGN KEY(document_id)
                    REFERENCES documents(document_id)
                    ON DELETE CASCADE
            )
        """)
        
        # Create index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_document_id 
            ON ai_analysis(document_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_analysis_classification 
            ON ai_analysis(classification)
        """)
        
        # Insert or update analysis
        cursor.execute("""
            INSERT INTO ai_analysis (
                document_id, summary, entities, relevance_score,
                classification, privilege_risk, topics, action_items, review_notes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (document_id)
            DO UPDATE SET
                summary = EXCLUDED.summary,
                entities = EXCLUDED.entities,
                relevance_score = EXCLUDED.relevance_score,
                classification = EXCLUDED.classification,
                privilege_risk = EXCLUDED.privilege_risk,
                topics = EXCLUDED.topics,
                action_items = EXCLUDED.action_items,
                review_notes = EXCLUDED.review_notes,
                analyzed_at = CURRENT_TIMESTAMP
        """, (
            document_id,
            analysis.get("summary"),
            json.dumps(analysis.get("entities", {})),
            analysis.get("relevance_score", 0),
            analysis.get("classification", "Unknown"),
            analysis.get("privilege_risk", 0),
            json.dumps(analysis.get("topics", [])),
            json.dumps(analysis.get("action_items", [])),
            analysis.get("review_notes")
        ))
        
        conn.commit()
        print(f"✅ Stored AI analysis for {document_id}")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error storing analysis: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def analyze_documents(limit: Optional[int] = None, document_id: Optional[str] = None):
    """Analyze documents with AI."""
    
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get documents to analyze
    if document_id:
        cursor.execute("""
            SELECT d.document_id, d.subject, d.body_text, c.email as custodian_email
            FROM documents d
            LEFT JOIN custodians c ON d.custodian_id = c.id
            WHERE d.document_id = %s
        """, (document_id,))
    else:
        # Get documents that haven't been analyzed yet
        cursor.execute("""
            SELECT d.document_id, d.subject, d.body_text, c.email as custodian_email
            FROM documents d
            LEFT JOIN custodians c ON d.custodian_id = c.id
            LEFT JOIN ai_analysis a ON d.document_id = a.document_id
            WHERE a.id IS NULL
            ORDER BY d.collected_at DESC
            {}
        """.format(f"LIMIT {limit}" if limit else ""))
    
    documents = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if not documents:
        print("ℹ️  No documents to analyze")
        return
    
    print(f"\n🤖 Analyzing {len(documents)} document(s) with AI...\n")
    
    for i, doc in enumerate(documents, 1):
        print(f"[{i}/{len(documents)}] Analyzing: {doc['document_id']}")
        print(f"  Subject: {doc['subject'][:60]}...")
        
        try:
            # Analyze with AI
            analysis = analyze_document_with_ai(
                subject=doc['subject'] or "",
                body=doc['body_text'] or "",
                custodian=doc['custodian_email'] or "Unknown"
            )
            
            # Store results
            store_ai_analysis(doc['document_id'], analysis)
            
            # Print summary
            print(f"  Classification: {analysis.get('classification')}")
            print(f"  Relevance: {analysis.get('relevance_score')}/100")
            print(f"  Summary: {analysis.get('summary', '')[:80]}...")
            print()
            
        except Exception as e:
            print(f"  ❌ Error: {e}\n")
            continue


def show_analysis_report():
    """Show summary report of AI analysis."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("\n" + "=" * 70)
    print("📊 AI ANALYSIS REPORT")
    print("=" * 70 + "\n")
    
    # Total analyzed
    cursor.execute("SELECT COUNT(*) as count FROM ai_analysis")
    total = cursor.fetchone()['count']
    print(f"📄 Total Documents Analyzed: {total}\n")
    
    # By classification
    cursor.execute("""
        SELECT classification, COUNT(*) as count
        FROM ai_analysis
        GROUP BY classification
        ORDER BY count DESC
    """)
    print("📊 By Classification:")
    for row in cursor.fetchall():
        print(f"  {row['classification']:20} {row['count']:>5} docs")
    
    # Average relevance
    cursor.execute("SELECT AVG(relevance_score) as avg_score FROM ai_analysis")
    avg_score = cursor.fetchone()['avg_score']
    if avg_score:
        print(f"\n📈 Average Relevance Score: {avg_score:.1f}/100")
    
    # High relevance documents
    cursor.execute("""
        SELECT document_id, summary, relevance_score, classification
        FROM ai_analysis
        WHERE relevance_score >= 70
        ORDER BY relevance_score DESC
        LIMIT 5
    """)
    high_relevance = cursor.fetchall()
    
    if high_relevance:
        print(f"\n🔥 Top {len(high_relevance)} High-Relevance Documents:")
        for doc in high_relevance:
            print(f"\n  ID: {doc['document_id']}")
            print(f"  Relevance: {doc['relevance_score']}/100 | {doc['classification']}")
            print(f"  Summary: {doc['summary'][:100]}...")
    
    # Privilege risk
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM ai_analysis
        WHERE privilege_risk >= 50
    """)
    privilege_count = cursor.fetchone()['count']
    if privilege_count > 0:
        print(f"\n⚖️  Potential Privileged Documents: {privilege_count}")
    
    print("\n" + "=" * 70 + "\n")
    
    cursor.close()
    conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="AI Document Analyzer for E-Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--analyze-all", action="store_true", help="Analyze all unanalyzed documents")
    parser.add_argument("--batch", type=int, metavar="N", help="Analyze N documents")
    parser.add_argument("--document", metavar="ID", help="Analyze specific document")
    parser.add_argument("--report", action="store_true", help="Show analysis report")
    
    args = parser.parse_args()
    
    load_env()
    
    try:
        if args.report:
            show_analysis_report()
        elif args.document:
            analyze_documents(document_id=args.document)
        elif args.batch:
            analyze_documents(limit=args.batch)
        elif args.analyze_all:
            analyze_documents()
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()

