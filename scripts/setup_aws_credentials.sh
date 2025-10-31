#!/bin/bash
# Helper script to set up AWS credentials for ediscovery ingestion

set -e

echo "🔐 AWS Credentials Setup Helper"
echo "================================"
echo ""
echo "This script will help you configure AWS credentials safely."
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed."
    echo ""
    echo "📥 Install it first:"
    echo "   macOS:   brew install awscli"
    echo "   Linux:   pip install awscli"
    echo "   Windows: Download from aws.amazon.com/cli"
    echo ""
    exit 1
fi

echo "✅ AWS CLI is installed"
echo ""

# Check current AWS configuration
echo "🔍 Checking current AWS configuration..."
echo ""

if aws sts get-caller-identity &> /dev/null; then
    echo "✅ You already have AWS credentials configured!"
    echo ""
    echo "Current AWS Identity:"
    aws sts get-caller-identity --output table
    echo ""
    
    read -p "Do you want to use these credentials? (y/n): " use_existing
    if [[ "$use_existing" == "y" || "$use_existing" == "Y" ]]; then
        echo ""
        echo "✅ Great! You're ready to go."
        echo ""
        echo "Your credentials are already set. You can now run:"
        echo "  python scripts/run_ingest.py --config configs/s3_production.json"
        echo ""
        exit 0
    fi
fi

echo "❌ No valid AWS credentials found (or you want to use different ones)"
echo ""
echo "📋 You need to get AWS credentials first. Here's how:"
echo ""
echo "STEP 1: Log into AWS Console"
echo "  → Go to: https://console.aws.amazon.com/"
echo "  → Log in with your AWS account"
echo ""
echo "STEP 2: Navigate to IAM"
echo "  → Search for 'IAM' in the top search bar"
echo "  → Click 'IAM' (Identity and Access Management)"
echo ""
echo "STEP 3: Create Access Key"
echo "  → Click 'Users' in the left sidebar"
echo "  → Click your username (or create a new user)"
echo "  → Click 'Security credentials' tab"
echo "  → Scroll to 'Access keys' section"
echo "  → Click 'Create access key'"
echo "  → Choose 'Application running outside AWS'"
echo "  → Click 'Next' and then 'Create access key'"
echo ""
echo "STEP 4: Save Your Credentials"
echo "  → You'll see:"
echo "      - Access Key ID (starts with AKIA...)"
echo "      - Secret Access Key (long random string)"
echo "  → ⚠️  IMPORTANT: Copy these NOW - you won't see the secret again!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Have you created your access key? (y/n): " created_key

if [[ "$created_key" != "y" && "$created_key" != "Y" ]]; then
    echo ""
    echo "⏸️  No problem! Come back and run this script after you've created your access key."
    echo ""
    exit 0
fi

echo ""
echo "Great! Let's configure your credentials."
echo ""
echo "⚠️  SECURITY NOTE: Your credentials will be stored in ~/.aws/credentials"
echo "   This is the standard, secure location for AWS credentials."
echo ""

# Option 1: Use aws configure
echo "Choose configuration method:"
echo "  1) Interactive setup (recommended for beginners)"
echo "  2) Manual environment variables (for this session only)"
echo ""
read -p "Enter your choice (1 or 2): " config_method

if [[ "$config_method" == "1" ]]; then
    echo ""
    echo "Starting AWS CLI configuration..."
    echo ""
    echo "You'll be asked for:"
    echo "  1. AWS Access Key ID"
    echo "  2. AWS Secret Access Key"
    echo "  3. Default region (use: us-east-1)"
    echo "  4. Default output format (use: json)"
    echo ""
    
    aws configure
    
    echo ""
    echo "✅ Configuration complete!"
    echo ""
    echo "Testing your credentials..."
    
    if aws sts get-caller-identity &> /dev/null; then
        echo ""
        echo "🎉 SUCCESS! Your credentials work!"
        echo ""
        aws sts get-caller-identity --output table
        echo ""
    else
        echo ""
        echo "❌ Credentials test failed. Please check your access key and try again."
        echo ""
        exit 1
    fi
    
elif [[ "$config_method" == "2" ]]; then
    echo ""
    read -p "Enter your AWS Access Key ID: " access_key_id
    read -p "Enter your AWS Secret Access Key: " secret_access_key
    read -p "Enter your AWS Region (press Enter for us-east-1): " region
    
    region=${region:-us-east-1}
    
    export AWS_ACCESS_KEY_ID="$access_key_id"
    export AWS_SECRET_ACCESS_KEY="$secret_access_key"
    export AWS_DEFAULT_REGION="$region"
    
    echo ""
    echo "Testing your credentials..."
    
    if aws sts get-caller-identity &> /dev/null; then
        echo ""
        echo "🎉 SUCCESS! Your credentials work!"
        echo ""
        aws sts get-caller-identity --output table
        echo ""
        echo "⚠️  NOTE: These credentials are only set for this terminal session."
        echo "   To make them permanent, run: aws configure"
        echo ""
        echo "For now, you can run:"
        echo "  python scripts/run_ingest.py --config configs/s3_production.json"
        echo ""
    else
        echo ""
        echo "❌ Credentials test failed. Please check your access key and try again."
        echo ""
        exit 1
    fi
else
    echo ""
    echo "Invalid choice. Please run the script again."
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ AWS Credentials are configured!"
echo ""
echo "Next steps:"
echo "  1. Edit configs/s3_production.json with your tenant ID"
echo "  2. Run: python scripts/run_ingest.py --config configs/s3_production.json"
echo ""
echo "Or use the automated production test:"
echo "  ./scripts/test_s3_production.sh"
echo ""

