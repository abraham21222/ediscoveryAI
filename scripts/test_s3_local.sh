#!/bin/bash
# Test script for S3 ingestion with LocalStack

set -e

echo "🚀 Starting S3 Local Testing with LocalStack"
echo "============================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start LocalStack
echo "📦 Starting LocalStack..."
docker-compose up -d localstack

# Wait for LocalStack to be ready
echo "⏳ Waiting for LocalStack to be ready..."
sleep 5

# Check LocalStack health
if ! curl -s http://localhost:4566/_localstack/health | grep -q '"s3": "available"'; then
    echo "❌ Error: LocalStack S3 is not available"
    exit 1
fi

echo "✅ LocalStack is ready"

# Set LocalStack credentials
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Run ingestion pipeline
echo ""
echo "📥 Running ingestion pipeline with S3 backend..."
python scripts/run_ingest.py \
    --config configs/s3_local_testing.json \
    --log-level INFO

# Verify data in S3
echo ""
echo "🔍 Verifying data in LocalStack S3..."

# List buckets
echo ""
echo "Buckets:"
aws --endpoint-url=http://localhost:4566 s3 ls

# List objects in bucket
echo ""
echo "Objects in bucket:"
aws --endpoint-url=http://localhost:4566 s3 ls s3://ediscovery-local-test-tenant --recursive --human-readable | head -20

# Count total objects
OBJECT_COUNT=$(aws --endpoint-url=http://localhost:4566 s3 ls s3://ediscovery-local-test-tenant --recursive | wc -l)
echo ""
echo "Total objects in bucket: $OBJECT_COUNT"

# Download and display a sample file
echo ""
echo "Sample document content:"
aws --endpoint-url=http://localhost:4566 s3 cp \
    s3://ediscovery-local-test-tenant/sample_seed_data/default/mock-email-0/body.txt \
    - 2>/dev/null | head -10

# Show object metadata
echo ""
echo "Sample object metadata:"
aws --endpoint-url=http://localhost:4566 s3api head-object \
    --bucket ediscovery-local-test-tenant \
    --key sample_seed_data/default/mock-email-0/metadata.json \
    | jq -r '.Metadata'

echo ""
echo "✅ S3 ingestion test completed successfully!"
echo ""
echo "To explore the data:"
echo "  aws --endpoint-url=http://localhost:4566 s3 ls s3://ediscovery-local-test-tenant --recursive"
echo ""
echo "To stop LocalStack:"
echo "  docker-compose down"

