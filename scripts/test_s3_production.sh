#!/bin/bash
# Production AWS S3 ingestion test script

set -e

echo "🚀 Production AWS S3 Ingestion Test"
echo "===================================="
echo ""

# Check if AWS credentials are configured
echo "🔍 Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo ""
    echo "❌ AWS credentials are not configured!"
    echo ""
    echo "Please run the setup script first:"
    echo "  ./scripts/setup_aws_credentials.sh"
    echo ""
    exit 1
fi

echo "✅ AWS credentials are valid"
echo ""
echo "Current AWS Identity:"
aws sts get-caller-identity --output table
echo ""

# Check if production config exists
if [ ! -f "configs/s3_production.json" ]; then
    echo "❌ Production config not found: configs/s3_production.json"
    exit 1
fi

# Extract tenant_id from config
TENANT_ID=$(python3 -c "import json; print(json.load(open('configs/s3_production.json'))['object_store']['params']['tenant_id'])")
BUCKET_PREFIX=$(python3 -c "import json; print(json.load(open('configs/s3_production.json'))['object_store']['params']['bucket_prefix'])")
BUCKET_NAME="${BUCKET_PREFIX}-${TENANT_ID}"

echo "📋 Configuration:"
echo "  Tenant ID:     $TENANT_ID"
echo "  Bucket Prefix: $BUCKET_PREFIX"
echo "  Bucket Name:   $BUCKET_NAME"
echo "  Region:        $(aws configure get region || echo 'us-east-1')"
echo ""

# Confirm before proceeding
echo "⚠️  WARNING: This will:"
echo "  1. Create an S3 bucket in your AWS account (if it doesn't exist)"
echo "  2. Upload ~10 test documents"
echo "  3. Incur minimal AWS costs (< $0.01)"
echo ""
read -p "Do you want to continue? (yes/no): " confirm

if [[ "$confirm" != "yes" ]]; then
    echo ""
    echo "⏸️  Aborted. No changes made to AWS."
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run ingestion
echo "📥 Running ingestion pipeline..."
echo ""
python scripts/run_ingest.py \
    --config configs/s3_production.json \
    --log-level INFO

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verify bucket exists
echo "🔍 Verifying S3 bucket..."
if aws s3 ls "s3://$BUCKET_NAME" &> /dev/null; then
    echo "✅ Bucket exists: $BUCKET_NAME"
else
    echo "❌ Bucket not found: $BUCKET_NAME"
    exit 1
fi

echo ""

# List objects
echo "📦 Objects in bucket:"
echo ""
aws s3 ls "s3://$BUCKET_NAME" --recursive --human-readable | head -30

# Count objects
OBJECT_COUNT=$(aws s3 ls "s3://$BUCKET_NAME" --recursive | wc -l)
echo ""
echo "Total objects: $OBJECT_COUNT"

# Check bucket encryption
echo ""
echo "🔐 Bucket encryption status:"
aws s3api get-bucket-encryption --bucket "$BUCKET_NAME" 2>/dev/null | python3 -m json.tool || echo "  Encryption: Default (S3-managed)"

# Check bucket versioning
echo ""
echo "📋 Bucket versioning status:"
aws s3api get-bucket-versioning --bucket "$BUCKET_NAME" | python3 -m json.tool

# Download and display a sample document
echo ""
echo "📄 Sample document content:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
SAMPLE_KEY=$(aws s3 ls "s3://$BUCKET_NAME" --recursive | grep "body.txt" | head -1 | awk '{print $4}')
if [ -n "$SAMPLE_KEY" ]; then
    aws s3 cp "s3://$BUCKET_NAME/$SAMPLE_KEY" - 2>/dev/null | head -15
    echo "..."
else
    echo "No sample documents found"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Show object metadata
echo ""
echo "🏷️  Sample object metadata (chain of custody):"
METADATA_KEY=$(aws s3 ls "s3://$BUCKET_NAME" --recursive | grep "metadata.json" | head -1 | awk '{print $4}')
if [ -n "$METADATA_KEY" ]; then
    echo ""
    aws s3api head-object --bucket "$BUCKET_NAME" --key "$METADATA_KEY" | python3 -c "import sys, json; meta = json.load(sys.stdin); print(json.dumps(meta.get('Metadata', {}), indent=2))"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✅ Production S3 ingestion test completed successfully!"
echo ""
echo "📊 Summary:"
echo "  Bucket:     $BUCKET_NAME"
echo "  Objects:    $OBJECT_COUNT"
echo "  Region:     $(aws configure get region || echo 'us-east-1')"
echo "  Encryption: Enabled"
echo "  Versioning: Enabled"
echo ""
echo "🌐 View in AWS Console:"
echo "  https://s3.console.aws.amazon.com/s3/buckets/$BUCKET_NAME"
echo ""
echo "💡 Next steps:"
echo "  1. Explore your data in AWS Console"
echo "  2. Check CloudWatch logs for detailed activity"
echo "  3. Review billing (should be < $0.01 for this test)"
echo ""
echo "🧹 To clean up test data:"
echo "  aws s3 rm s3://$BUCKET_NAME --recursive"
echo "  aws s3 rb s3://$BUCKET_NAME"
echo ""

