#!/usr/bin/env python3
"""
Create a realistic Enron load file package (DAT + TEXT files)
for testing the Relativity integration UI.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def create_loadfile_package(output_dir: Path, num_documents: int = 1000):
    """
    Create a load file package from Enron sample data.
    
    Args:
        output_dir: Directory to create the package in
        num_documents: Number of documents to include (max 500k)
    """
    
    # Create output directories
    output_dir.mkdir(parents=True, exist_ok=True)
    text_dir = output_dir / "TEXT"
    text_dir.mkdir(exist_ok=True)
    
    # Path to Enron sample data
    enron_data_dir = Path(__file__).parent.parent / "_evidence" / "sample_seed_data"
    
    if not enron_data_dir.exists():
        print(f"❌ Enron sample data not found at: {enron_data_dir}")
        print("Please run the Enron ingestion first.")
        sys.exit(1)
    
    # Collect all email folders
    email_folders = sorted([d for d in enron_data_dir.iterdir() if d.is_dir()])
    
    if len(email_folders) == 0:
        print(f"❌ No email folders found in: {enron_data_dir}")
        sys.exit(1)
    
    print(f"📂 Found {len(email_folders)} email folders")
    print(f"📊 Creating load file for {min(num_documents, len(email_folders))} documents...")
    
    # DAT file header (using thorn delimiter þ)
    dat_lines = []
    delimiter = "þ"
    
    # Header row
    headers = [
        "DOCID",
        "BATES_NUMBER", 
        "CUSTODIAN",
        "DATE_SENT",
        "SUBJECT",
        "FROM",
        "TO",
        "CC",
        "ATTACHMENT_COUNT",
        "FILE_SIZE",
        "FILE_TYPE",
        "TEXT_PATH",
        "MD5_HASH",
        "SOURCE",
    ]
    dat_lines.append(delimiter.join(headers))
    
    documents_created = 0
    
    for idx, email_folder in enumerate(email_folders[:num_documents]):
        try:
            # Read metadata
            metadata_file = email_folder / "metadata.json"
            body_file = email_folder / "body.txt"
            
            if not metadata_file.exists() or not body_file.exists():
                continue
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            with open(body_file, 'r', encoding='utf-8', errors='ignore') as f:
                body_text = f.read()
            
            # Generate document ID
            doc_id = f"ENRON{idx+1:06d}"
            bates = f"ENRON-{idx+1:08d}"
            
            # Extract metadata
            custodian = metadata.get('custodian', 'Unknown')
            date_sent = metadata.get('date_sent', '')
            subject = metadata.get('subject', '(No Subject)')
            from_addr = metadata.get('from', '')
            to_addrs = '; '.join(metadata.get('to', []))
            cc_addrs = '; '.join(metadata.get('cc', []))
            attachment_count = len(metadata.get('attachments', []))
            
            # Calculate file size and hash
            file_size = len(body_text.encode('utf-8'))
            md5_hash = hashlib.md5(body_text.encode('utf-8')).hexdigest()
            
            # Text file path
            text_filename = f"{doc_id}.txt"
            text_path = f"TEXT/{text_filename}"
            
            # Write text file
            text_file_path = text_dir / text_filename
            with open(text_file_path, 'w', encoding='utf-8') as f:
                f.write(body_text)
            
            # Clean up fields for DAT (escape delimiters and newlines)
            def clean_field(value):
                if not value:
                    return ""
                # Replace delimiter and newlines
                value = str(value).replace(delimiter, " ")
                value = value.replace("\n", " ").replace("\r", " ")
                value = value.replace("  ", " ").strip()
                return value
            
            # Build DAT row
            row = [
                doc_id,
                bates,
                clean_field(custodian),
                clean_field(date_sent),
                clean_field(subject),
                clean_field(from_addr),
                clean_field(to_addrs),
                clean_field(cc_addrs),
                str(attachment_count),
                str(file_size),
                "Email",
                text_path,
                md5_hash,
                "Enron Email Archive",
            ]
            
            dat_lines.append(delimiter.join(row))
            documents_created += 1
            
            if documents_created % 100 == 0:
                print(f"  ✓ Processed {documents_created} documents...")
        
        except Exception as e:
            print(f"  ⚠️  Error processing {email_folder.name}: {e}")
            continue
    
    # Write DAT file
    dat_file = output_dir / "ENRON_PRODUCTION.DAT"
    with open(dat_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dat_lines))
    
    print(f"\n✅ Load file package created!")
    print(f"   📄 DAT file: {dat_file}")
    print(f"   📁 TEXT files: {text_dir} ({documents_created} files)")
    print(f"   📊 Total size: {sum(f.stat().st_size for f in text_dir.glob('*.txt')) / 1024 / 1024:.1f} MB")
    print(f"\n🎯 Ready to upload to the Relativity UI!")
    
    return dat_file, text_dir, documents_created


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Create Enron load file package')
    parser.add_argument('--output', '-o', default='/Users/abrahambloom/Downloads/enron_loadfile',
                        help='Output directory for load file package')
    parser.add_argument('--count', '-n', type=int, default=1000,
                        help='Number of documents to include (default: 1000)')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    print("\n" + "=" * 60)
    print("📦 Enron Load File Package Generator")
    print("=" * 60)
    
    dat_file, text_dir, count = create_loadfile_package(output_dir, args.count)
    
    print("\n" + "=" * 60)
    print("🚀 Next Steps:")
    print("=" * 60)
    print(f"1. Open: http://localhost:8080/relativity")
    print(f"2. Upload: {dat_file}")
    print(f"3. The system will automatically find the TEXT files")
    print(f"4. Click 'Run AI Analysis'")
    print(f"5. Documents will be ingested into your database!")
    print("=" * 60 + "\n")

