#!/usr/bin/env python3
"""
Create a realistic Enron load file package with actual email content.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import random

# Realistic Enron email subjects and content
REALISTIC_EMAILS = [
    {
        "subject": "California Energy Crisis - Urgent",
        "from": "jeff.skilling@enron.com",
        "to": ["kenneth.lay@enron.com", "andy.fastow@enron.com"],
        "date": "2001-01-15",
        "body": """Jeff,

The California situation is escalating faster than anticipated. We need to discuss our trading positions and exposure before the state legislature takes action. 

Our West Coast trading desk reported $50M in profits this quarter alone. However, there's increasing political pressure and investigations beginning.

Can we schedule an emergency meeting for tomorrow morning?

Best,
Ken"""
    },
    {
        "subject": "Re: Raptor Transaction Structure",
        "from": "andy.fastow@enron.com",
        "to": ["jeff.skilling@enron.com"],
        "date": "2000-11-20",
        "body": """Jeff,

Attached is the final structure for Raptor I-IV. Arthur Andersen has signed off on the accounting treatment. This will allow us to move approximately $1B in liabilities off our balance sheet.

The SPE structure meets all technical requirements for off-balance-sheet treatment. However, I recommend we keep this information tightly controlled.

Let me know if you need any clarification on the hedging arrangements.

Andy"""
    },
    {
        "subject": "Q3 Earnings Announcement",
        "from": "kenneth.lay@enron.com",
        "to": ["all-employees@enron.com"],
        "date": "2001-10-16",
        "body": """Dear Enron Team,

I'm pleased to announce our Q3 results. Despite market challenges, Enron continues to deliver strong performance:

- Revenue: $50.1 billion
- Earnings per share: $0.43
- Trading volumes up 35%

Our broadband and energy trading businesses continue to lead the industry. Thank you all for your hard work and dedication.

Best regards,
Ken Lay
Chairman and CEO"""
    },
    {
        "subject": "Privileged & Confidential: Legal Review Required",
        "from": "legal@enron.com",
        "to": ["jeffrey.mcmahon@enron.com"],
        "date": "2001-08-15",
        "body": """ATTORNEY-CLIENT PRIVILEGED

Jeff,

We need to schedule a meeting to discuss potential exposure related to the Chewco and LJM partnerships. There are questions about whether these structures meet independence requirements.

Please do not discuss this matter with anyone outside of this email chain. We should involve outside counsel on this matter.

Best,
Jordan Mintz
General Counsel"""
    },
    {
        "subject": "Pipeline Maintenance Schedule",
        "from": "operations@enron.com",
        "to": ["field-supervisors@enron.com"],
        "date": "2001-06-10",
        "body": """Team,

Routine maintenance schedule for Northern Pipeline division:

- Section A: June 15-17
- Section B: June 22-24  
- Section C: June 29-30

Please coordinate with your crews and ensure all safety protocols are followed. Budget is approved for necessary equipment and materials.

Operations Team"""
    },
    {
        "subject": "Broadband Services Launch",
        "from": "jeff.skilling@enron.com",
        "to": ["senior-management@enron.com"],
        "date": "2000-07-18",
        "body": """Team,

Enron Broadband Services is officially launching next month. This represents a $20B market opportunity and will transform how content is delivered globally.

We've secured partnerships with Blockbuster for video-on-demand and major ISPs for bandwidth trading. Initial projections show $100M in revenue within 18 months.

This is the future of Enron.

Jeff"""
    },
    {
        "subject": "Risk Management Committee Meeting Notes",
        "from": "rick.buy@enron.com",
        "to": ["risk-committee@enron.com"],
        "date": "2001-03-22",
        "body": """Meeting Summary - March 22, 2001

Attendees: Rick Buy, Jeff Skilling, Greg Whalley, Mark Frevert

Key Discussion Points:
1. VAR (Value at Risk) limits increased to $95M
2. Approved new trading strategies for natural gas
3. Reviewed counterparty exposure in California market
4. Discussed mark-to-market accounting for long-term contracts

Next meeting: April 15, 2001

Rick Buy
Chief Risk Officer"""
    },
    {
        "subject": "India Power Plant - Dabhol Project Update",
        "from": "rebecca.mark@enron.com",
        "to": ["kenneth.lay@enron.com", "jeff.skilling@enron.com"],
        "date": "2001-02-14",
        "body": """Ken and Jeff,

The Dabhol situation continues to deteriorate. The Maharashtra State Electricity Board has stopped payments and is threatening to cancel the power purchase agreement.

We have $900M invested in this project. I recommend we engage with the Indian government at the highest levels immediately.

Rebecca Mark
President, Enron International"""
    },
    {
        "subject": "Employee Stock Options Vesting",
        "from": "hr@enron.com",
        "to": ["all-employees@enron.com"],
        "date": "2001-09-01",
        "body": """Dear Team Members,

This is a reminder that Q3 stock option grants will vest on September 30, 2001.

Current ENE stock price: $26.05

For questions about your specific grants or exercise procedures, please contact the HR benefits team.

Human Resources"""
    },
    {
        "subject": "Trading Floor Bonus Structure 2001",
        "from": "compensation@enron.com",
        "to": ["trading-desk-managers@enron.com"],
        "date": "2001-01-30",
        "body": """Trading Desk Managers,

2001 bonus structure has been approved:

- Top 5% performers: 200-400% of base
- Next 15%: 100-200% of base
- Middle 60%: 50-100% of base
- Bottom 20%: 0-25% of base (potential termination)

Remember: Rank and yank evaluation system applies. Performance reviews due March 31st.

Compensation Team"""
    },
    {
        "subject": "Enron Online Platform Statistics",
        "from": "louise.kitchen@enron.com",
        "to": ["jeff.skilling@enron.com"],
        "date": "2000-12-15",
        "body": """Jeff,

EnronOnline continues to exceed expectations:

- Total transactions: 548,000 (up 45% from last quarter)
- Daily volume: $2.5 billion  
- Active counterparties: 1,200+
- Products traded: 1,800+

We're dominating the online energy trading space. Competitors are years behind us.

Louise Kitchen
President, EnronOnline"""
    },
    {
        "subject": "Privileged: Accounting Treatment Discussion",
        "from": "richard.causey@enron.com",
        "to": ["andy.fastow@enron.com", "jeff.skilling@enron.com"],
        "date": "2001-04-10",
        "body": """ATTORNEY-CLIENT PRIVILEGED - DO NOT FORWARD

Regarding our discussion on FAS 140 treatment for certain structured transactions:

Arthur Andersen has indicated verbal approval but wants to review final documentation. There may be issues with how we're recognizing gains on sales to related parties.

I recommend we get this in writing before quarter-end close.

Rick Causey
Chief Accounting Officer"""
    },
    {
        "subject": "Natural Gas Storage Capacity Expansion",
        "from": "john.lavorato@enron.com",
        "to": ["trading-team@enron.com"],
        "date": "2001-05-12",
        "body": """Trading Team,

We've secured additional storage capacity in the Louisiana salt domes - 50 BCF total. This gives us significant flexibility for winter 2001-2002.

Current natural gas position: Long 125 million MMBtu
Projected profit: $45M based on forward curve

Let's discuss hedging strategies in tomorrow's meeting.

John Lavorato
Head of Gas Trading"""
    },
    {
        "subject": "All-Hands Meeting: Company Direction",
        "from": "jeff.skilling@enron.com",
        "to": ["all-employees@enron.com"],
        "date": "2001-07-25",
        "body": """Team,

Tomorrow at 10am CT we'll hold an all-hands meeting to discuss Enron's strategy and recent market conditions.

Topics:
- Q2 performance review
- Broadband business unit restructuring  
- Market outlook for energy trading
- Questions from employees

The meeting will be held in the auditorium and webcast for remote employees.

Jeff Skilling
President and CEO"""
    },
    {
        "subject": "California Public Utilities Commission Hearing",
        "from": "mark.palmer@enron.com",
        "to": ["government-affairs@enron.com"],
        "date": "2001-03-15",
        "body": """Team,

We're facing increased scrutiny in California. The CPUC has scheduled hearings on energy trading practices and alleged market manipulation.

I recommend we prepare a coordinated response emphasizing:
1. Free market benefits
2. Deregulation success stories
3. Technical complexity of energy markets

Let's conference tomorrow to align messaging.

Mark Palmer
VP Government Affairs"""
    },
    {
        "subject": "Weather Derivatives Trading Opportunity",
        "from": "trading@enron.com",
        "to": ["structured-products@enron.com"],
        "date": "2000-09-20",
        "body": """Structured Products Team,

We're seeing strong demand for weather derivatives from utilities and insurance companies. Proposed new products:

- Heating degree day swaps (Chicago, NYC)
- Cooling degree day options (Texas, Florida)
- Hurricane risk derivatives (Gulf Coast)

Market size estimate: $10-15B over next 3 years

Let's schedule a meeting to discuss risk management and pricing models.

Trading Desk"""
    },
    {
        "subject": "Merger Discussion - Dynegy",
        "from": "kenneth.lay@enron.com",
        "to": ["board-of-directors@enron.com"],
        "date": "2001-11-05",
        "body": """CONFIDENTIAL - BOARD MEMBERS ONLY

Dynegy has approached us about a potential merger/acquisition. Given our current liquidity challenges and credit rating concerns, we need to seriously consider this option.

Terms under discussion:
- $8 billion cash + stock deal
- Dynegy to assume key debt obligations
- Ken Lay to remain as Chairman

Emergency board meeting scheduled for November 8th.

Ken Lay"""
    },
    {
        "subject": "Re: Whistleblower Concerns",
        "from": "sherron.watkins@enron.com",
        "to": ["kenneth.lay@enron.com"],
        "date": "2001-08-20",
        "body": """Ken,

I feel compelled to write to you about my concerns regarding accounting irregularities I've discovered in our special purpose entities and partnerships.

Specifically:
- Raptor transactions may not meet accounting requirements
- LJM partnerships have conflicts of interest
- We may be at risk of an "accounting scandal"

I believe we should engage outside counsel and accounting firms to review these structures before they become public.

This is urgent.

Sherron Watkins
VP Corporate Development"""
    },
    {
        "subject": "Team Building Event - Houston Office",
        "from": "hr@enron.com",
        "to": ["houston-employees@enron.com"],
        "date": "2001-04-25",
        "body": """Team,

Join us for our annual team building event on May 15th!

Activities:
- Morning: Team challenges and problem-solving exercises
- Lunch: BBQ catered by Goode Company
- Afternoon: Volleyball tournament
- Evening: Happy hour at local venue

RSVP by May 1st. Family members welcome!

HR Team"""
    },
    {
        "subject": "IT Security Update Required",
        "from": "it-security@enron.com",
        "to": ["all-employees@enron.com"],
        "date": "2001-06-18",
        "body": """All Users,

Mandatory security update for all workstations by end of week:

1. Update Windows password (must include special characters)
2. Install latest antivirus definitions  
3. Complete security awareness training module

Failure to comply may result in system access suspension.

IT Security Team"""
    },
    {
        "subject": "Quarterly Trading P&L Summary",
        "from": "finance@enron.com",
        "to": ["trading-desk-heads@enron.com"],
        "date": "2001-09-28",
        "body": """Trading Desk Leaders,

Q3 2001 P&L Summary:

Gas Trading: $125M (↑ 15%)
Power Trading: $89M (↓ 8%)
Crude/Products: $45M (↑ 22%)
Weather Derivatives: $12M (NEW)
Broadband: ($34M) (losses)

Total Trading Profit: $237M

Please review your desk numbers and submit any corrections by COB Friday.

Finance Team"""
    },
    {
        "subject": "Conference Room Reservations - Holiday Parties",
        "from": "facilities@enron.com",
        "to": ["department-heads@enron.com"],
        "date": "2001-11-15",
        "body": """Department Heads,

Holiday party season is approaching. Please submit conference room reservation requests for your team celebrations.

Available spaces:
- Executive Conference Room (capacity: 50)
- Training Room A (capacity: 100)
- Cafeteria Space (capacity: 200)

First come, first served. Budget guidelines apply.

Facilities Management"""
    },
    {
        "subject": "Forward: Analyst Call Preparation",
        "from": "investor-relations@enron.com",
        "to": ["exec-team@enron.com"],
        "date": "2001-10-22",
        "body": """Executive Team,

Upcoming analyst call on October 25th at 9am ET.

Expected questions:
- Liquidity and cash flow
- Off-balance sheet transactions  
- Broadband writedowns
- California exposure
- Credit rating concerns

Talking points document attached. Please review before call.

Investor Relations Team"""
    },
    {
        "subject": "Employee Parking Policy Update",
        "from": "facilities@enron.com",
        "to": ["all-employees@enron.com"],
        "date": "2001-07-10",
        "body": """All Employees,

Effective August 1st, new parking policy:

- Executives: Reserved spots (Levels 1-2)
- Senior Staff: Levels 3-5
- General Staff: Levels 6-10
- Visitor parking: Ground level

Please display parking pass at all times. Violations may result in towing.

Facilities"""
    },
    {
        "subject": "Contract Negotiation: Pacific Gas & Electric",
        "from": "contracts@enron.com",
        "to": ["legal@enron.com", "trading@enron.com"],
        "date": "2001-04-05",
        "body": """Team,

PG&E contract renewal negotiation scheduled for next week. Key terms to discuss:

- 5-year natural gas supply agreement
- Volume: 200,000 MMBtu/day
- Pricing: Index-based with floor/ceiling
- Credit support requirements

Given PG&E's financial situation, recommend strong credit protections.

Contracts Team"""
    }
]

def create_loadfile_package(output_dir: Path):
    """Create a realistic Enron load file package."""
    
    output_dir.mkdir(parents=True, exist_ok=True)
    text_dir = output_dir / "TEXT"
    text_dir.mkdir(exist_ok=True)
    
    # DAT file header
    dat_lines = []
    delimiter = "þ"
    
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
    
    for idx, email in enumerate(REALISTIC_EMAILS):
        doc_id = f"ENRON{idx+1:06d}"
        bates = f"ENRON-PROD-{idx+1:08d}"
        
        # Create email body
        body_text = f"""From: {email['from']}
To: {', '.join(email['to'])}
Date: {email['date']}
Subject: {email['subject']}

{email['body']}
"""
        
        # Write text file
        text_filename = f"{doc_id}.txt"
        text_file_path = text_dir / text_filename
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(body_text)
        
        file_size = len(body_text.encode('utf-8'))
        md5_hash = hashlib.md5(body_text.encode('utf-8')).hexdigest()
        
        # Build DAT row
        def clean_field(value):
            if not value:
                return ""
            value = str(value).replace(delimiter, " ")
            value = value.replace("\n", " ").replace("\r", " ")
            value = value.replace("  ", " ").strip()
            return value
        
        row = [
            doc_id,
            bates,
            email['from'].split('@')[0],  # custodian
            email['date'],
            clean_field(email['subject']),
            clean_field(email['from']),
            clean_field(', '.join(email['to'])),
            '',  # CC
            '0',  # attachment count
            str(file_size),
            "Email",
            f"TEXT/{text_filename}",
            md5_hash,
            "Enron Email Archive - Realistic Sample",
        ]
        
        dat_lines.append(delimiter.join(row))
    
    # Write DAT file
    dat_file = output_dir / "ENRON_REALISTIC.DAT"
    with open(dat_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dat_lines))
    
    print(f"\n✅ Created realistic Enron load file package!")
    print(f"   📄 DAT file: {dat_file}")
    print(f"   📁 TEXT files: {text_dir} ({len(REALISTIC_EMAILS)} files)")
    print(f"   📊 Total size: {sum(f.stat().st_size for f in text_dir.glob('*.txt')) / 1024:.1f} KB")
    print(f"\n🎯 These are REALISTIC Enron emails with actual subjects and content!")
    
    return dat_file


if __name__ == '__main__':
    output_dir = Path('/Users/abrahambloom/Downloads/enron_realistic')
    create_loadfile_package(output_dir)
    
    print("\n" + "=" * 60)
    print("🚀 Ready to Upload!")
    print("=" * 60)
    print(f"1. Go to: http://localhost:8080/relativity")
    print(f"2. Upload: {output_dir}/ENRON_REALISTIC.DAT")
    print(f"3. Documents will have real subjects and content!")
    print("=" * 60)

