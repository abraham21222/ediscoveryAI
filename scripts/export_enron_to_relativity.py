#!/usr/bin/env python3
"""
Export Enron dataset to Relativity load file format.

This creates a .DAT file from your existing Enron data,
simulating what a processing vendor would deliver.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def export_to_relativity_dat(source_dir: Path, output_dat: Path, limit: int = 100):
    """
    Export Enron emails to Relativity .DAT format.
    
    Args:
        source_dir: Directory containing Enron email JSON files
        output_dat: Output .DAT file path
        limit: Maximum number of documents to export
    """
    print(f"Exporting Enron data to Relativity format...")
    print(f"Source: {source_dir}")
    print(f"Output: {output_dat}")
    print(f"Limit: {limit} documents")
    print()
    
    # Find all email JSON files
    email_files = list(source_dir.glob("**/*.json"))
    if not email_files:
        print(f"❌ No JSON files found in {source_dir}")
        return
    
    email_files = email_files[:limit]
    print(f"Found {len(email_files)} email files")
    
    # Create output directory
    output_dat.parent.mkdir(parents=True, exist_ok=True)
    
    # Write DAT file with thorn delimiter
    with open(output_dat, 'w', encoding='utf-8') as f:
        # Header row
        f.write('þDocIDþBatesNumberþCustodianþDateSentþSubjectþFromþToþCCþFilePathþTextPath\n')
        
        # Data rows
        for idx, email_file in enumerate(email_files, start=1):
            try:
                # Read email data
                with open(email_file) as ef:
                    email = json.load(ef)
                
                # Extract fields
                doc_id = f"ENRON_{idx:06d}"
                bates = f"ENRON{idx:08d}"
                custodian = email.get('From', 'unknown@enron.com')
                date_sent = email.get('Date', '')
                subject = email.get('Subject', '(No Subject)').replace('\n', ' ').replace('\r', ' ')
                from_addr = email.get('From', '')
                to_addr = email.get('To', '')
                cc_addr = email.get('Cc', '')
                
                # File paths (simulate processing vendor structure)
                native_path = f"\\\\NATIVES\\\\{doc_id}.eml"
                text_path = f"\\\\TEXT\\\\{doc_id}.txt"
                
                # Clean fields (remove delimiter and newlines)
                def clean(s):
                    return str(s).replace('þ', '|').replace('\n', ' ').replace('\r', ' ')
                
                # Write row
                f.write(f'þ{clean(doc_id)}')
                f.write(f'þ{clean(bates)}')
                f.write(f'þ{clean(custodian)}')
                f.write(f'þ{clean(date_sent)}')
                f.write(f'þ{clean(subject)}')
                f.write(f'þ{clean(from_addr)}')
                f.write(f'þ{clean(to_addr)}')
                f.write(f'þ{clean(cc_addr)}')
                f.write(f'þ{clean(native_path)}')
                f.write(f'þ{clean(text_path)}')
                f.write('\n')
                
            except Exception as e:
                print(f"Warning: Error processing {email_file}: {e}")
                continue
    
    print(f"✓ Exported {len(email_files)} documents to {output_dat}")
    print()
    print("Next steps:")
    print(f"  1. Review the DAT file: cat {output_dat}")
    print(f"  2. Test parsing: python test_relativity_integration_enron.py")


def main():
    """Main execution."""
    # Look for Enron data
    possible_dirs = [
        Path('data/enron/sample'),
        Path('data/enron'),
        Path('_objects/enron-emails'),
    ]
    
    enron_dir = None
    for dir_path in possible_dirs:
        if dir_path.exists():
            enron_dir = dir_path
            break
    
    if not enron_dir:
        print("❌ Enron data not found. Looking in:")
        for d in possible_dirs:
            print(f"   - {d}")
        print()
        print("Please run the Enron ingestion first:")
        print("  python scripts/download_enron.py")
        print("  python scripts/ingest_enron.py --config configs/enron_test.json")
        return
    
    # Export to DAT
    output_dat = Path('test_data/ENRON_LOADFILE.DAT')
    export_to_relativity_dat(enron_dir, output_dat, limit=100)


if __name__ == '__main__':
    main()

