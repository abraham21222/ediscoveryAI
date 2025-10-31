#!/usr/bin/env python3
"""Interactive script to configure tenant settings for production."""

import json
import sys
from pathlib import Path

def main():
    print("🔧 Tenant Configuration Helper")
    print("=" * 50)
    print()
    print("This script will help you customize your production configuration.")
    print()
    
    # Load current config
    config_path = Path("configs/s3_production.json")
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path) as f:
        config = json.load(f)
    
    print("📋 Current Configuration:")
    print(f"  Tenant ID:     {config['object_store']['params']['tenant_id']}")
    print(f"  Bucket Prefix: {config['object_store']['params']['bucket_prefix']}")
    print(f"  Region:        {config['object_store']['params']['region']}")
    print()
    
    # Ask if they want to change
    response = input("Do you want to change these settings? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print()
        print("✅ No changes made. Current configuration will be used.")
        return
    
    print()
    print("━" * 50)
    print()
    
    # Get tenant ID
    print("🏢 TENANT ID")
    print("  This identifies your organization/client.")
    print("  Examples: 'acme-corp', 'orion-law', 'test-client'")
    print("  Rules: lowercase, hyphens allowed, no spaces")
    print()
    tenant_id = input(f"Enter tenant ID [{config['object_store']['params']['tenant_id']}]: ").strip()
    if not tenant_id:
        tenant_id = config['object_store']['params']['tenant_id']
    
    # Validate tenant_id
    if not tenant_id.replace('-', '').replace('_', '').isalnum():
        print()
        print("❌ Invalid tenant ID. Use only letters, numbers, hyphens, and underscores.")
        sys.exit(1)
    
    tenant_id = tenant_id.lower()
    
    print()
    
    # Get bucket prefix
    print("📦 BUCKET PREFIX")
    print("  Prefix for your S3 bucket name.")
    print("  Examples: 'ediscovery-prod', 'ediscovery-staging', 'ediscovery-dev'")
    print()
    bucket_prefix = input(f"Enter bucket prefix [{config['object_store']['params']['bucket_prefix']}]: ").strip()
    if not bucket_prefix:
        bucket_prefix = config['object_store']['params']['bucket_prefix']
    
    bucket_prefix = bucket_prefix.lower()
    
    print()
    
    # Get region
    print("🌍 AWS REGION")
    print("  Common regions:")
    print("    us-east-1      (N. Virginia) - Default, lowest cost")
    print("    us-west-2      (Oregon)")
    print("    eu-west-1      (Ireland)")
    print("    eu-central-1   (Frankfurt)")
    print()
    region = input(f"Enter AWS region [{config['object_store']['params']['region']}]: ").strip()
    if not region:
        region = config['object_store']['params']['region']
    
    print()
    
    # Ask about KMS
    print("🔐 KMS ENCRYPTION (Optional)")
    print("  Do you have a KMS key ARN for encryption?")
    print("  If no, we'll use S3-managed encryption (still secure).")
    print()
    current_kms = config['object_store']['params'].get('kms_key_id', '')
    if current_kms:
        print(f"  Current KMS key: {current_kms}")
    
    use_kms = input("Do you have a KMS key ARN? (yes/no): ").strip().lower()
    
    kms_key_id = None
    if use_kms in ['yes', 'y']:
        print()
        print("  KMS key ARN format: arn:aws:kms:REGION:ACCOUNT:key/KEY-ID")
        kms_key_id = input("Enter KMS key ARN: ").strip()
        if not kms_key_id.startswith('arn:aws:kms:'):
            print()
            print("⚠️  Warning: KMS ARN doesn't look valid. Proceeding anyway...")
    
    print()
    print("━" * 50)
    print()
    
    # Show summary
    bucket_name = f"{bucket_prefix}-{tenant_id}"
    print("📋 CONFIGURATION SUMMARY")
    print()
    print(f"  Tenant ID:       {tenant_id}")
    print(f"  Bucket Prefix:   {bucket_prefix}")
    print(f"  Bucket Name:     {bucket_name}")
    print(f"  AWS Region:      {region}")
    print(f"  KMS Encryption:  {kms_key_id if kms_key_id else 'S3-managed (default)'}")
    print()
    print("💰 Estimated Costs:")
    print(f"  Storage:  $0.023/GB/month (STANDARD class)")
    print(f"  Requests: $0.005 per 1,000 PUT requests")
    print(f"  Test run: < $0.01")
    print()
    
    # Confirm
    confirm = input("Save this configuration? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print()
        print("⏸️  Configuration not saved.")
        return
    
    # Update config
    config['object_store']['params']['tenant_id'] = tenant_id
    config['object_store']['params']['bucket_prefix'] = bucket_prefix
    config['object_store']['params']['region'] = region
    
    if kms_key_id:
        config['object_store']['params']['kms_key_id'] = kms_key_id
    elif 'kms_key_id' in config['object_store']['params']:
        # Remove KMS key if user chose not to use one
        del config['object_store']['params']['kms_key_id']
    
    # Save config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print()
    print("✅ Configuration saved to configs/s3_production.json")
    print()
    print("🚀 Next steps:")
    print("  1. Verify your AWS credentials are set:")
    print("       aws sts get-caller-identity")
    print()
    print("  2. Run the production test:")
    print("       ./scripts/test_s3_production.sh")
    print()
    print("  3. Or run ingestion directly:")
    print("       python scripts/run_ingest.py --config configs/s3_production.json")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("⏸️  Interrupted. No changes saved.")
        sys.exit(0)

