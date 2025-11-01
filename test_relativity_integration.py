#!/usr/bin/env python3
"""
Test Relativity Integration

This script demonstrates the complete workflow:
1. Parse a Relativity load file (.DAT)
2. Run AI analysis on documents
3. Export enriched results for upload back to Relativity
"""

import sys
from pathlib import Path
from integrations.relativity_loader import (
    RelativityLoadFileParser,
    RelativityEnrichmentExporter,
    RelativityDocument
)

def create_sample_dat_file():
    """Create a sample Relativity DAT file for testing."""
    sample_dat = Path('sample_loadfile.dat')
    
    # Sample data with thorn delimiter (þ)
    content = """þDocIDþBatesNumberþCustodianþDateSentþSubjectþFromþToþFilePathþTextPath
þEMAIL001þABC00001þjohn.doe@company.comþ2024-01-15þQuarterly Resultsþjohn.doe@company.comþcfo@company.comþ\\NATIVES\\EMAIL001.msgþ\\TEXT\\EMAIL001.txt
þEMAIL002þABC00002þjane.smith@company.comþ2024-01-16þRe: Budget Discussionþjane.smith@company.comþjohn.doe@company.comþ\\NATIVES\\EMAIL002.emlþ\\TEXT\\EMAIL002.txt
þEMAIL003þABC00003þlegal@company.comþ2024-01-17þConfidential: Attorney-Client Communicationþlegal@company.comþexternal.counsel@lawfirm.comþ\\NATIVES\\EMAIL003.msgþ\\TEXT\\EMAIL003.txt
þDOC0001þABC00004þjohn.doe@company.comþ2024-01-20þContract Draft v3þN/AþN/Aþ\\NATIVES\\DOC0001.docxþ\\TEXT\\DOC0001.txt
þEMAIL004þABC00005þhr@company.comþ2024-01-22þTeam Lunch Plansþhr@company.comþteam@company.comþ\\NATIVES\\EMAIL004.msgþ\\TEXT\\EMAIL004.txt
"""
    
    sample_dat.write_text(content, encoding='utf-8')
    print(f"✓ Created sample DAT file: {sample_dat}")
    return sample_dat


def simulate_ai_analysis(doc: RelativityDocument) -> RelativityDocument:
    """
    Simulate AI analysis of a document.
    In production, this would call your actual AI models.
    """
    
    # Simple rule-based simulation for demo
    subject_lower = (doc.subject or '').lower()
    from_lower = (doc.from_field or '').lower()
    to_lower = (doc.to_field or '').lower()
    
    # Detect privilege
    if 'confidential' in subject_lower or 'attorney' in subject_lower:
        doc.ai_privileged = 'Yes'
        doc.ai_privilege_confidence = 0.95
    elif 'legal' in from_lower or 'counsel' in to_lower:
        doc.ai_privileged = 'Maybe'
        doc.ai_privilege_confidence = 0.72
    else:
        doc.ai_privileged = 'No'
        doc.ai_privilege_confidence = 0.98
    
    # Detect responsiveness
    if 'quarterly' in subject_lower or 'budget' in subject_lower or 'contract' in subject_lower:
        doc.ai_responsive = 'Yes'
        doc.ai_responsive_confidence = 0.89
    elif 'lunch' in subject_lower:
        doc.ai_responsive = 'No'
        doc.ai_responsive_confidence = 0.99
    else:
        doc.ai_responsive = 'Maybe'
        doc.ai_responsive_confidence = 0.65
    
    # Classify
    if doc.ai_privileged == 'Yes':
        doc.ai_classification = 'Privileged'
        doc.hot_score = 25
    elif doc.ai_responsive == 'Yes' and doc.ai_responsive_confidence > 0.85:
        doc.ai_classification = 'Relevant'
        doc.hot_score = 65
    elif doc.ai_responsive == 'No':
        doc.ai_classification = 'Routine'
        doc.hot_score = 5
    else:
        doc.ai_classification = 'Needs Review'
        doc.hot_score = 50
    
    # Extract topics (simple keyword extraction)
    topics = []
    if 'quarterly' in subject_lower or 'results' in subject_lower:
        topics.append('Financial Results')
    if 'budget' in subject_lower:
        topics.append('Budget Planning')
    if 'contract' in subject_lower:
        topics.append('Contract Negotiation')
    if 'legal' in subject_lower or 'attorney' in subject_lower:
        topics.append('Legal Communication')
    if 'lunch' in subject_lower:
        topics.append('Social')
    
    doc.ai_topics = topics if topics else ['General']
    
    return doc


def main():
    """Run complete test workflow."""
    print("="*70)
    print("Relativity Integration Test")
    print("="*70)
    print()
    
    # Step 1: Create sample data
    print("Step 1: Creating sample Relativity load file...")
    dat_file = create_sample_dat_file()
    print()
    
    # Step 2: Parse the DAT file
    print("Step 2: Parsing Relativity load file...")
    parser = RelativityLoadFileParser(dat_file)
    documents = parser.parse()
    
    print(f"✓ Parsed {len(documents)} documents")
    print(f"✓ Fields found: {', '.join(parser.get_field_names())}")
    print()
    
    # Step 3: Display sample documents
    print("Step 3: Sample documents:")
    print("-" * 70)
    for doc in documents[:3]:
        print(f"Doc ID: {doc.doc_id}")
        print(f"  Bates: {doc.bates_number}")
        print(f"  From: {doc.from_field}")
        print(f"  Subject: {doc.subject}")
        print()
    
    # Step 4: Run AI analysis
    print("Step 4: Running AI analysis...")
    analyzed_docs = []
    for doc in documents:
        analyzed_doc = simulate_ai_analysis(doc)
        analyzed_docs.append(analyzed_doc)
    
    print(f"✓ Analyzed {len(analyzed_docs)} documents")
    print()
    
    # Step 5: Display AI results
    print("Step 5: AI Analysis Results:")
    print("-" * 70)
    for doc in analyzed_docs:
        print(f"Doc ID: {doc.doc_id}")
        print(f"  Subject: {doc.subject}")
        print(f"  AI Responsive: {doc.ai_responsive} ({doc.ai_responsive_confidence:.0%} confidence)")
        print(f"  AI Privileged: {doc.ai_privileged} ({doc.ai_privilege_confidence:.0%} confidence)")
        print(f"  Classification: {doc.ai_classification}")
        print(f"  Hot Score: {doc.hot_score}/100")
        print(f"  Topics: {', '.join(doc.ai_topics)}")
        print()
    
    # Step 6: Export enrichment file
    print("Step 6: Exporting AI enrichment file...")
    output_file = Path('AI_ENRICHMENT.csv')
    exporter = RelativityEnrichmentExporter(output_file)
    exporter.export(analyzed_docs)
    
    print(f"✓ Exported to: {output_file}")
    print()
    
    # Step 7: Show summary statistics
    print("Step 7: Summary Statistics:")
    print("-" * 70)
    
    responsive_yes = sum(1 for d in analyzed_docs if d.ai_responsive == 'Yes')
    responsive_no = sum(1 for d in analyzed_docs if d.ai_responsive == 'No')
    responsive_maybe = sum(1 for d in analyzed_docs if d.ai_responsive == 'Maybe')
    
    privileged_yes = sum(1 for d in analyzed_docs if d.ai_privileged == 'Yes')
    privileged_maybe = sum(1 for d in analyzed_docs if d.ai_privileged == 'Maybe')
    
    hot_docs = sum(1 for d in analyzed_docs if d.hot_score > 80)
    
    print(f"Responsiveness:")
    print(f"  ✓ Responsive: {responsive_yes} ({responsive_yes/len(analyzed_docs)*100:.0f}%)")
    print(f"  ✗ Not Responsive: {responsive_no} ({responsive_no/len(analyzed_docs)*100:.0f}%)")
    print(f"  ? Maybe: {responsive_maybe} ({responsive_maybe/len(analyzed_docs)*100:.0f}%)")
    print()
    print(f"Privilege:")
    print(f"  ⚖️  Privileged: {privileged_yes}")
    print(f"  ? Maybe Privileged: {privileged_maybe}")
    print()
    print(f"Priority:")
    print(f"  🔥 Hot Documents: {hot_docs}")
    print()
    
    # Step 8: Cost savings calculation
    print("Step 8: Cost Savings Calculation:")
    print("-" * 70)
    
    total_docs = len(analyzed_docs)
    skip_review = responsive_no  # High-confidence "Not Responsive"
    human_review = total_docs - skip_review
    
    traditional_cost = total_docs * 1.50  # $1.50 per doc
    ai_cost = total_docs * 0.10  # $0.10 per doc for AI analysis
    review_cost = human_review * 1.50  # Only review non-skipped docs
    total_with_ai = ai_cost + review_cost
    savings = traditional_cost - total_with_ai
    
    print(f"Traditional Review:")
    print(f"  {total_docs} docs × $1.50/doc = ${traditional_cost:,.2f}")
    print()
    print(f"With AI:")
    print(f"  AI Analysis: {total_docs} docs × $0.10/doc = ${ai_cost:,.2f}")
    print(f"  Human Review: {human_review} docs × $1.50/doc = ${review_cost:,.2f}")
    print(f"  Total: ${total_with_ai:,.2f}")
    print()
    print(f"💰 Savings: ${savings:,.2f} ({savings/traditional_cost*100:.0f}%)")
    print()
    
    # Final message
    print("="*70)
    print("✅ Test Complete!")
    print("="*70)
    print()
    print("Next steps:")
    print("  1. Review AI_ENRICHMENT.csv")
    print("  2. This file can be uploaded to Relativity")
    print("  3. AI fields will populate in your review platform")
    print()
    print("To test with real data:")
    print("  1. Get a .DAT file from your processing vendor")
    print("  2. Run: python test_relativity_integration.py")
    print("  3. Review the enrichment output")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

