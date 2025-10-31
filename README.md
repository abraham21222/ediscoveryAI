# eDiscovery Data Ingestion Layer Blueprint

## 1. Why This Matters
Replacing traditional eDiscovery platforms with AI-first tooling demands an ingestion layer that can ingest, normalize, enrich, and secure massive volumes of heterogeneous evidence. This blueprint captures the initial solution direction, open questions, and a scaffolding implementation that we can iterate on quickly.

## 2. Market Snapshot (2024)
- Mature, consolidated incumbents (Relativity, Reveal, Exterro, Everlaw) still dominate with full-stack platforms.
- New entrants (Fylamynt, Disco, Alt-Law, Henchman, Spellbook, Latch, Altorney/Marc) compete on automation, AI summarization, and speed-to-insight rather than raw ingestion scale.
- Differentiation opportunity: opinionated AI workflows, tiered ingestion cost models, transparent defensibility (auditability of AI steps), and seamless hand-off from ingestion to review/co-pilot surfaces.
- Barriers to entry remain high because of compliance, discovery workflow depth, and expensive connectors/licensing. Winning requires deep integrations rather than just an LLM wrapper.

## 3. Data For Testing & Benchmarking
| Source | Dataset Ideas | Notes |
| --- | --- | --- |
| Public email corpora | Enron Email Dataset (Kaggle); CSET's GovDocs1; Avocado Research Email Collection | Available for research; requires PII scrubbing.
| Document dumps | SEC EDGAR filings; court opinions (CourtListener); EU/US public procurement docs | Good for OCR + metadata extraction tests.
| Forensics | NIST CFReDS disk images; Digital Corpora E01 sample images | Useful for validating chain-of-custody metadata and big-binary handling.
| Synthetic | Generate templated emails, NDAs, contracts with LLMs; mix with redacted samples | Enables controlled label creation for downstream AI tasks.
| Partner pilots | Law firms' historical cases under NDA, hashed storage | Need compliance workflows and anonymization playbooks.

Action items to unlock richer private data:
1. Identify pilot firm(s) willing to share historical matters (need contact + NDA).
2. Clarify data retention policy + on-prem vs. cloud deployment constraints.
3. Capture required certifications (SOC2 Type II, FedRAMP moderate, ISO 27001, HIPAA where applicable).

## 4. Target Company Architecture (First 12 Months)
- **Product**: modular platform with ingestion, AI workbench (summaries, clustering, privilege detection), reviewer UI, audit tools.
- **Teams**: ingestion/core platform; AI/ML; reviewer experience; compliance & legal ops; infra/DevSecOps.
- **Deployment**: dual footprint—managed SaaS on AWS multi-account landing zone and an air-gapped customer-managed Helm bundle for sensitive tenants.
- **Data Governance**: dedicated trust team for access approvals, logging, breach response, and certification maintenance.

## 5. Ingestion Layer Requirements
1. Handle batch and streaming inputs from:
   - Email (IMAP/POP, Microsoft Graph, Google Workspace).
   - Cloud storage (S3, Azure Blob, GDrive, Box, SharePoint).
   - Forensic collections (Relativity load files, E01/ZIP uploads, FTP/SFTP drops).
2. Normalize to a common evidence schema (document, message, attachment, custodians, legal hold flags).
3. Apply processing steps: deduplication, hash calculation, OCR (where needed), entity extraction, privilege heuristics.
4. Guarantee defensibility: preserve original, immutable copies; maintain chain-of-custody metadata.
5. Enforce granular RBAC, encryption, and detailed audit logging.
6. Support back-pressure control and retryable jobs to cope with high-volume matters.

## 6. Architecture Overview
```
Source Connectors -> Ingestion Orchestrator -> Normalization & Enrichment -> Storage Targets -> Event Bus -> Downstream AI/Review
```

- **Source Connectors**: pluggable, stateless workers per source type. Configurable polling or webhook triggers.
- **Ingestion Orchestrator**: queue-backed pipeline (Temporal on EKS + AWS SQS/Kinesis for fan-out).
- **Normalization**: convert raw payload into canonical `EvidenceDocument` model; attach metadata, process attachments recursively.
- **Enrichment**: OCR via AWS Textract (fallback: on-prem Tesseract), PII/entity detection (AWS Comprehend Legal + spaCy), LLM tagging in a guarded environment.
- **Storage**: immutable object store (per-tenant S3 buckets with Glacier lifecycle) + metadata index (Amazon Aurora PostgreSQL + Amazon OpenSearch) + vector store (pgvector extensions) for AI feature discovery.
- **Observability**: metrics (Amazon Managed Prometheus), structured logs (CloudWatch + OpenTelemetry), distributed tracing (AWS X-Ray/OpenTelemetry).
- **Security**: envelope encryption with per-tenant AWS KMS CMKs, secrets via AWS Secrets Manager + HashiCorp Vault for air-gapped deployments.

## 7. Implementation Roadmap
1. **MVP iteration (Weeks 0-3)**
   - Microsoft 365 connector using Graph delta queries writing to S3 and Aurora staging tables.
   - Normalizer capturing custodians, subjects, attachments; chain-of-custody manifest generation.
   - OCR fallback and metadata indexing in Aurora + OpenSearch.
   - CLI tool to trigger ingest + basic Grafana dashboard for throughput/error metrics.
2. **Hardening (Weeks 4-8)**
   - GMail/GDrive connectors; Box and SharePoint Online ingestion.
   - Audit log service (Kinesis Firehose -> S3 + Athena), legal hold tagging, retention policies.
   - Deduplication using SHA-256 + SSDeep; begin privilege classifier training using labeled corpora.
3. **Scale + AI hooks (Weeks 9-16)**
   - Temporal workflows with activity heartbeats, back-pressure, and retries.
   - Enrichment with NER, privilege classifier, topic clustering, and vector embeddings.
   - Event bridge to downstream reviewer UI and analytics lake (Iceberg tables on S3).

## 8. Operating Decisions & Baseline Assumptions
- **Cloud Footprint**: AWS multi-account landing zone (ingestion-prod, ingestion-nonprod, shared-services). Primary region `us-east-1`, secondary `us-west-2` for DR. Terraform + Terragrunt for IaC.
- **Runtime Platform**: Amazon EKS (Fargate profiles for stateless connectors, self-managed node groups for heavy OCR). Temporal, Kafka (MSK), and Redis (Elasticache) deployed per environment.
- **Tenant Isolation**: per-organization S3 bucket & KMS CMK, dedicated Aurora schema, isolated OpenSearch index. Optionally provision per-matter logical partitions with scoped IAM roles.
- **Throughput Target**: ingest 500k documents/day, 2 TB/day peak, 30-day backlog flush within 72 hours. Concurrency achieved via autoscaling connectors + step-function triggered batch jobs.
- **Data Retention & Residency**: default 7-year retention with legal hold overrides; EU customers deployed in eu-central-1 with KMS residency guarantees.
- **Security Controls**: TLS 1.3 everywhere, mutual TLS for internal services, AWS WAF + CloudFront for APIs, automated chain-of-custody logs appended to write-once S3 (Object Lock).
- **OCR & Language Coverage**: managed Textract for English, Spanish, French, German; fallback to Tesseract with traineddata packs for Portuguese and Italian. Document quality scoring decides when fallback is invoked.
- **AI/ML Dependencies**: prefer managed services (Textract, Comprehend, Rekognition for handwriting). Open-source stack (spaCy, fastText, sentence-transformers) containerized for on-prem/air-gapped, with model registry in S3 (signed artifacts).
- **Compliance Roadmap**: SOC2 Type II within 9 months, ISO 27001 within 12, FedRAMP Moderate ready architecture defined (GovCloud path), CJIS readiness for public-sector pilots.

## 9. Credential & Access Checklist
| Data Source | Access Method | Credentials / Artifacts | Notes |
| --- | --- | --- | --- |
| Microsoft 365 (Exchange/SharePoint/OneDrive) | Microsoft Graph delta queries | Azure AD tenant ID, client ID/secret, application registration with `Mail.Read`, `Sites.Read.All`, `User.Read.All`; list of mailbox IDs | Use per-tenant app registrations. Service principal stored in AWS Secrets Manager. |
| Google Workspace (Gmail/Drive) | Admin SDK + Gmail/Drive APIs | Service account JSON key with domain-wide delegation, subject user email, scopes `https://www.googleapis.com/auth/gmail.readonly`, `.../drive.readonly` | Rotate keys every 90 days; leverage Google Cloud Secret Manager for air-gapped handoff. |
| Box Enterprise | Box Events + Bulk Download API | JWT app config (JSON), client secret, public/private keypair, enterprise ID, user mapping CSV | Enable governance API tier for legal holds. |
| Forensic Collections | SFTP or AWS Transfer Family | SSH key pair, IP allow list, checksum manifest (MD5/SHA256), optional AS2 certs | Disk images staged to S3 Glacier Deep Archive with parallel checksum verification. |
| On-Prem File Shares | Hybrid connector appliance | Site-to-site VPN, connector appliance token, share credentials (SMB/NFS service accounts) | Appliance publishes into ingestion queue via secure MQTT over TLS. |
| Third-Party Review Exports (Relativity, Nuix) | Load files ingest | Upload credentials, format spec (OPT, DAT), field mapping templates | Parser adapters stored per vendor; metadata validation library enforces mappings. |

## 10. Current Deliverables In Repo
- `ingestion/` Python package with connector scaffolding and orchestrator skeleton.
- `configs/aws_foundation.json` sample configuration aligning with the operating assumptions (keeps mock connectors disabled by default).
- `scripts/run_ingest.py` CLI entrypoint for local testing (uses mocked sources until credentials provided).
- Extensive inline TODO markers indicating where real credentials, queue URIs, or SDK integration work is required.

### ✅ **NEW: Production S3 Object Store (2025-10-31)**
- **S3ObjectStore** class with enterprise-grade features:
  - Per-tenant bucket isolation (`{prefix}-{tenant_id}`)
  - Multipart uploads for files >5MB
  - Server-side encryption (KMS or S3-managed)
  - S3 versioning for immutable storage
  - Chain of custody tracking via object metadata
  - Automatic retry with exponential backoff
  - Public access blocking by default
- **LocalStack Support** for local S3 testing without AWS costs
- **Configuration Files**:
  - `configs/s3_production.json` - Production AWS configuration
  - `configs/s3_local_testing.json` - LocalStack development configuration
- **Docker Compose** environment with LocalStack, PostgreSQL, OpenSearch, Redis
- **Testing Script**: `scripts/test_s3_local.sh` for automated local testing
- **Comprehensive Documentation**: See `S3_SETUP_GUIDE.md` for setup, configuration, and troubleshooting

## 11. Quick Start with S3

### Local Development (LocalStack)
```bash
# Install dependencies
pip install -r requirements.txt

# Start LocalStack
docker-compose up -d localstack

# Run ingestion with S3 backend
export AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
python scripts/run_ingest.py --config configs/s3_local_testing.json

# Or use the automated test script
./scripts/test_s3_local.sh
```

### Production AWS
```bash
# Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# Update configs/s3_production.json with your tenant_id and bucket_prefix
# Run ingestion
python scripts/run_ingest.py --config configs/s3_production.json
```

### ✅ **NEW: Microsoft Graph Connector (2025-10-31)**
- **Production-ready Microsoft 365/Outlook email ingestion**:
  - OAuth2 authentication using MSAL (client credentials flow)
  - Automatic token refresh and caching
  - Pagination with @odata.nextLink support
  - Attachment downloading with base64 decoding
  - Rate limiting handling (429 responses)
  - Exponential backoff retry logic
  - Folder-based filtering (Inbox, Sent Items, etc.)
  - Date range filtering for targeted collection
  - Full metadata extraction (recipients, timestamps, conversation IDs)
  - Chain of custody tracking
- **Configuration File**: `configs/microsoft_graph.json`
- **Setup Guide**: `~/Downloads/MICROSOFT_GRAPH_SETUP_GUIDE.md` (comprehensive Azure AD setup)
- **Test Script**: `scripts/test_microsoft_graph.py` for validating connectivity

## 11. Quick Start with Microsoft Graph

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp env.template .env
```

### Azure AD Setup (One-time)
1. Follow the comprehensive guide: `~/Downloads/MICROSOFT_GRAPH_SETUP_GUIDE.md`
2. Create Azure AD app registration
3. Grant `Mail.Read` and `User.Read.All` permissions
4. Create client secret
5. Copy credentials to `.env` file

### Test Connection
```bash
# Set credentials in .env file, then:
python scripts/test_microsoft_graph.py --mailbox user@yourcompany.com

# Expected output:
# ✓ Access token acquired successfully
# ✓ Mailbox access verified
# ✓ Retrieved sample messages
# ✓ Successfully downloaded attachments
# 🎉 All tests passed!
```

### Run Production Ingestion
```bash
# Update configs/microsoft_graph.json with your settings
python scripts/run_ingest.py --config configs/microsoft_graph.json

# Or with custom mailbox
python scripts/run_ingest.py \
  --config configs/microsoft_graph.json \
  --override mailbox=ceo@company.com
```

## 12. Next Steps You Can Trigger
1. ✅ **S3 Object Store**: Complete (per-tenant buckets, multipart uploads, encryption)
2. ✅ **Microsoft Graph Connector**: Complete (OAuth2, pagination, attachments, rate limiting)
3. 🔄 **PostgreSQL Metadata Store**: Replace SQLite with Aurora/RDS for production scale
4. 🔄 **OpenSearch Integration**: Add full-text search and advanced querying
5. 🔄 **Google Workspace Connector**: Implement Gmail/Drive ingestion
6. 🔄 **KMS Envelope Encryption**: Client-side encryption layer before S3 upload
7. 🔄 **Audit Logging**: Kinesis Firehose for compliance and monitoring
8. 🔄 **Delta Queries**: Incremental sync for Microsoft Graph

---
_Last updated: 2025-10-31_
