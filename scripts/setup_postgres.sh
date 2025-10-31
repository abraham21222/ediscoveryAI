#!/bin/bash

# PostgreSQL Setup Helper Script
# This script helps you set up PostgreSQL for ediscovery metadata storage

set -e

echo "╔════════════════════════════════════════════════════════╗"
echo "║  PostgreSQL Setup for E-Discovery Platform            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

echo "Choose your PostgreSQL setup option:"
echo ""
echo "  1) AWS RDS PostgreSQL (Production - Recommended)"
echo "  2) Local PostgreSQL (Development - Mac)"
echo "  3) Cancel"
echo ""
read -p "Enter your choice (1-3): " choice

case $choice in
  1)
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║  AWS RDS PostgreSQL Setup                              ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    echo "I'll create a small PostgreSQL database on AWS RDS."
    echo ""
    echo "📋 Database Specifications:"
    echo "  - Instance Class: db.t3.micro (Free Tier Eligible)"
    echo "  - Storage: 20 GB SSD"
    echo "  - Engine: PostgreSQL 15"
    echo "  - Estimated Cost: ~$15/month (or FREE if eligible)"
    echo ""
    read -p "Continue? (y/n): " confirm
    
    if [[ "$confirm" != "y" ]]; then
      echo "Setup cancelled."
      exit 0
    fi
    
    echo ""
    echo "Creating RDS PostgreSQL instance..."
    
    # Generate a secure random password
    DB_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-16)
    
    # Create RDS instance
    aws rds create-db-instance \
      --db-instance-identifier ediscovery-metadata-db \
      --db-instance-class db.t3.micro \
      --engine postgres \
      --engine-version 15.14 \
      --master-username ediscovery \
      --master-user-password "$DB_PASSWORD" \
      --allocated-storage 20 \
      --storage-type gp2 \
      --storage-encrypted \
      --publicly-accessible \
      --backup-retention-period 7 \
      --no-multi-az \
      --db-name ediscovery_metadata \
      --port 5432 \
      --tags Key=Project,Value=ediscovery Key=Environment,Value=production
    
    echo ""
    echo "✅ RDS instance creation started!"
    echo ""
    echo "📝 Save these credentials securely:"
    echo "  Database Name: ediscovery_metadata"
    echo "  Username: ediscovery"
    echo "  Password: $DB_PASSWORD"
    echo ""
    echo "⏳ The database will be ready in 5-10 minutes."
    echo ""
    echo "To check status, run:"
    echo "  aws rds describe-db-instances --db-instance-identifier ediscovery-metadata-db --query 'DBInstances[0].Endpoint.Address'"
    echo ""
    echo "Once ready, I'll give you the connection string to add to your config."
    ;;
    
  2)
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║  Local PostgreSQL Setup (Mac)                         ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
    
    # Check if Homebrew is installed
    if ! command -v brew &> /dev/null; then
      echo "❌ Homebrew not found. Installing Homebrew first..."
      echo "Visit: https://brew.sh"
      exit 1
    fi
    
    echo "Installing PostgreSQL via Homebrew..."
    brew install postgresql@15
    
    echo ""
    echo "Starting PostgreSQL service..."
    brew services start postgresql@15
    
    sleep 3
    
    echo ""
    echo "Creating database and user..."
    createdb ediscovery_metadata || true
    psql -d postgres -c "CREATE USER ediscovery WITH PASSWORD 'ediscovery_dev_password';" || true
    psql -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE ediscovery_metadata TO ediscovery;" || true
    psql -d ediscovery_metadata -c "GRANT ALL ON SCHEMA public TO ediscovery;" || true
    
    echo ""
    echo "✅ PostgreSQL installed and running!"
    echo ""
    echo "📝 Database credentials:"
    echo "  Host: localhost"
    echo "  Port: 5432"
    echo "  Database: ediscovery_metadata"
    echo "  Username: ediscovery"
    echo "  Password: ediscovery_dev_password"
    echo ""
    
    # Initialize the schema
    echo "Initializing database schema..."
    PGPASSWORD='ediscovery_dev_password' psql -h localhost -U ediscovery -d ediscovery_metadata -f scripts/init_db.sql
    
    echo ""
    echo "✅ Database schema created successfully!"
    echo ""
    echo "To connect manually:"
    echo "  psql -h localhost -U ediscovery -d ediscovery_metadata"
    ;;
    
  3)
    echo "Setup cancelled."
    exit 0
    ;;
    
  *)
    echo "Invalid choice."
    exit 1
    ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Next Steps                                            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "1. Update configs/postgres_production.json with your credentials"
echo "2. Run the ingestion pipeline:"
echo "   python3 scripts/run_ingest.py --config configs/postgres_production.json"
echo "3. Query your data with SQL!"
echo ""

