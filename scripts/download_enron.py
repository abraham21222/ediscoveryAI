#!/usr/bin/env python3
"""
Download and prepare a subset of the Enron email dataset for testing.
The Enron dataset contains ~500k emails from 150 users.
We'll download a small subset for testing.
"""

import os
import sys
import json
import email
import mailbox
from pathlib import Path
import urllib.request
import tarfile
import shutil

def download_enron_subset():
    """Download a small subset of Enron emails."""
    
    print("📧 Enron Email Dataset Downloader\n")
    print("=" * 60)
    
    # Create data directory
    data_dir = Path("data/enron")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # We'll use the preprocessed Enron dataset from Kaggle/CMU
    # For testing, let's download just a few mailboxes
    
    print("\n🔍 Enron Dataset Info:")
    print("  • Total emails: ~500,000")
    print("  • Total users: ~150")
    print("  • Time period: 1998-2002")
    print("  • Public domain: Yes")
    
    print("\n📦 For testing, we'll create a smaller sample...")
    print("  • Target: 100-200 emails from key custodians")
    print("  • Focus: Executive communications")
    
    # Option 1: Download from a preprocessed source
    url = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
    
    print(f"\n⏬ Downloading from: {url}")
    print("⚠️  Warning: This is a 423MB file. Continue? (y/n): ", end='')
    
    # For automation, we'll assume yes
    response = "y"
    
    if response.lower() != 'y':
        print("❌ Download cancelled.")
        return None
    
    # Download
    tar_path = data_dir / "enron_mail.tar.gz"
    
    if tar_path.exists():
        print(f"✅ Archive already exists: {tar_path}")
    else:
        print(f"⏬ Downloading to {tar_path}...")
        print("   This may take a few minutes...")
        
        try:
            urllib.request.urlretrieve(url, tar_path)
            print(f"✅ Downloaded: {tar_path}")
        except Exception as e:
            print(f"❌ Download failed: {e}")
            print("\n💡 Alternative: Use a smaller sample")
            return create_sample_enron_emails(data_dir)
    
    # Extract just a subset
    extract_dir = data_dir / "maildir"
    
    if extract_dir.exists():
        print(f"✅ Already extracted: {extract_dir}")
    else:
        print(f"📦 Extracting subset...")
        try:
            with tarfile.open(tar_path, 'r:gz') as tar:
                # Extract only a few key mailboxes
                key_users = ['kenneth-lay', 'jeffrey-skilling', 'andrew-fastow', 
                            'sherri-sera', 'greg-whalley']
                
                members = tar.getmembers()
                subset = [m for m in members if any(user in m.name for user in key_users)][:200]
                
                print(f"   Extracting {len(subset)} files from key custodians...")
                for member in subset:
                    tar.extract(member, extract_dir)
                
                print(f"✅ Extracted to: {extract_dir}")
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return create_sample_enron_emails(data_dir)
    
    return extract_dir


def create_sample_enron_emails(data_dir):
    """Create a small sample of synthetic Enron-style emails for testing."""
    print("\n🔨 Creating sample Enron-style emails for testing...")
    
    sample_dir = data_dir / "sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    
    # Sample emails based on real Enron scenarios
    sample_emails = [
        {
            "from": "kenneth.lay@enron.com",
            "to": "jeff.skilling@enron.com",
            "subject": "Confidential: Q4 Earnings Discussion",
            "date": "2001-10-15",
            "body": """Jeff,
            
We need to discuss the Q4 projections with our legal counsel before the board meeting. 
The accounting treatment for the SPE transactions is becoming a concern.

I've asked our attorneys to review the mark-to-market positions. This stays between us for now.

Ken

[ATTORNEY-CLIENT PRIVILEGED]"""
        },
        {
            "from": "jeff.skilling@enron.com",
            "to": "andrew.fastow@enron.com",
            "subject": "RE: LJM Partnership Structure",
            "date": "2001-08-22",
            "body": """Andy,
            
The board has questions about the LJM structure. Can you prepare a summary of:
1. Total capital committed
2. Transaction flow with Enron
3. Related party disclosure requirements

We need this before the audit committee meeting next week.

Jeff"""
        },
        {
            "from": "sherri.sera@enron.com",
            "to": "kenneth.lay@enron.com",
            "subject": "Analyst Call - Talking Points",
            "date": "2001-09-10",
            "body": """Ken,
            
For tomorrow's analyst call, here are the key messages:
- Strong recurring revenues from wholesale trading
- California situation is stabilizing
- Broadband business showing 40% growth
- Maintain earnings guidance for FY2001

Attached are the prepared remarks and Q&A scenarios.

Sherri"""
        },
        {
            "from": "greg.whalley@enron.com",
            "to": "trading-desk@enron.com",
            "subject": "California Power Market Update",
            "date": "2001-01-18",
            "body": """Team,
            
California ISO prices hit $1,400/MWh today. Our positions are showing significant gains.

Key points for today:
- Continue normal trading activities
- Document all communications
- Route California positions through standard channels
- No emails discussing bidding strategies

Questions? Call me directly.

Greg"""
        },
        {
            "from": "legal@enron.com",
            "to": "kenneth.lay@enron.com",
            "subject": "PRIVILEGED: SEC Inquiry Response",
            "date": "2001-11-01",
            "body": """ATTORNEY-CLIENT PRIVILEGED AND CONFIDENTIAL

Ken,

The SEC has requested documents related to the Chewco and LJM partnerships. 
We are coordinating with outside counsel (Vinson & Elkins) on the response.

Recommend we:
1. Conduct internal review of all related party transactions
2. Preserve all documents and communications
3. Schedule attorney review of public disclosures
4. Prepare talking points for potential press inquiries

We'll brief you tomorrow at 9am.

Jordan Mintz
VP & General Counsel"""
        },
        {
            "from": "andrew.fastow@enron.com",
            "to": "michael.kopper@enron.com",
            "subject": "Raptor Vehicle Updates",
            "date": "2001-03-15",
            "body": """Mike,
            
Need to review the Raptor vehicle marks for Q1 close. The equity positions are underwater 
but we have the credit capacity to support them through the structured notes.

Let's meet Tuesday to review the accounting treatment with Arthur Andersen.

Also - keep this off email going forward. Let's discuss in person.

Andy"""
        },
        {
            "from": "hr@enron.com",
            "to": "all-employees@enron.com",
            "subject": "401(k) Plan Update",
            "date": "2001-10-29",
            "body": """Dear Colleagues,

Due to a planned system upgrade, the 401(k) plan will have a blackout period 
from October 29 through November 13, 2001.

During this time, you will not be able to:
- Make trades in your account
- Change contribution rates
- Request loans or distributions

Normal plan operations will resume November 14.

Thank you for your patience.

HR Department"""
        },
        {
            "from": "risk-management@enron.com",
            "to": "risk-committee@enron.com",
            "subject": "Daily VAR Report - October 2001",
            "date": "2001-10-18",
            "body": """Risk Committee,

Daily VAR Summary:
- Total Firm VAR: $85 million (95% confidence)
- Largest exposures: Natural gas, power, broadband
- Limit utilization: 92%
- New limit breaches: None

Concentration risks:
- California power: $2.1 billion notional
- Gas storage: $1.8 billion marked to market
- Fiber optic capacity: $450 million

Liquidity metrics remain within policy thresholds.

Rick Buy
Chief Risk Officer"""
        }
    ]
    
    # Write emails to files
    email_files = []
    for i, email_data in enumerate(sample_emails):
        filename = sample_dir / f"email_{i+1:03d}.json"
        with open(filename, 'w') as f:
            json.dump(email_data, f, indent=2)
        email_files.append(filename)
        print(f"   ✅ Created: {filename.name}")
    
    print(f"\n✅ Created {len(email_files)} sample Enron emails")
    print(f"📁 Location: {sample_dir}")
    
    return sample_dir


def parse_enron_emails(source_dir):
    """Parse Enron emails into our format."""
    print(f"\n📋 Parsing emails from: {source_dir}")
    
    emails = []
    
    if "sample" in str(source_dir):
        # Parse JSON sample emails
        for json_file in source_dir.glob("*.json"):
            with open(json_file) as f:
                data = json.load(f)
                emails.append(data)
    else:
        # Parse real Enron .eml files
        for eml_file in source_dir.rglob("*."):
            if eml_file.is_file():
                try:
                    with open(eml_file, 'r', errors='ignore') as f:
                        msg = email.message_from_file(f)
                        
                        emails.append({
                            "from": msg.get('From', 'unknown'),
                            "to": msg.get('To', 'unknown'),
                            "subject": msg.get('Subject', 'No Subject'),
                            "date": msg.get('Date', ''),
                            "body": msg.get_payload()
                        })
                except Exception as e:
                    continue
    
    print(f"✅ Parsed {len(emails)} emails")
    return emails


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("📧 ENRON EMAIL DATASET DOWNLOADER")
    print("=" * 60)
    
    # For testing, let's just create samples
    print("\n💡 For quick testing, we'll create sample Enron-style emails")
    print("   (Real dataset is 423MB - we can download if needed)")
    
    data_dir = Path("data/enron")
    email_dir = create_sample_enron_emails(data_dir)
    
    emails = parse_enron_emails(email_dir)
    
    print("\n" + "=" * 60)
    print(f"✅ Ready to ingest {len(emails)} Enron emails!")
    print("=" * 60)
    print(f"\n📁 Email location: {email_dir}")
    print("\nNext step: Run ingestion with these emails")
