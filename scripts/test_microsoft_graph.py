#!/usr/bin/env python3
"""Test script for Microsoft Graph connector connectivity and authentication.

This script validates:
- Azure AD authentication
- Access token acquisition
- Mailbox access permissions
- Folder enumeration
- Sample message retrieval
- Attachment handling

Run this before attempting full ingestion to catch configuration issues early.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion.config import ConnectorConfig
from ingestion.connectors.microsoft_graph import MicrosoftGraphConnector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_env_file(env_path: str = ".env") -> None:
    """Load environment variables from .env file."""
    env_file = Path(env_path)
    if not env_file.exists():
        logger.warning(f"Environment file not found: {env_path}")
        return

    logger.info(f"Loading environment from: {env_path}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()


def expand_env_vars(params: dict) -> dict:
    """Expand ${VAR} references in config params."""
    expanded = {}
    for key, value in params.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            expanded[key] = os.environ.get(env_var, value)
        else:
            expanded[key] = value
    return expanded


def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"✓ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"✗ {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"ℹ {message}")


def test_authentication(connector: MicrosoftGraphConnector) -> bool:
    """Test Azure AD authentication."""
    print_section("Test 1: Azure AD Authentication")

    try:
        print_info("Acquiring access token from Azure AD...")
        token = connector._get_access_token()

        if token:
            print_success("Access token acquired successfully")
            print_info(f"Token length: {len(token)} characters")
            print_info(f"Token expires at: {connector._token_expires_at}")
            return True
        else:
            print_error("Failed to acquire access token")
            return False

    except Exception as e:
        print_error(f"Authentication failed: {e}")
        return False


def test_mailbox_access(connector: MicrosoftGraphConnector) -> bool:
    """Test mailbox access and permissions."""
    print_section("Test 2: Mailbox Access")

    try:
        print_info(f"Testing access to mailbox: {connector._mailbox}")

        # Try to list folders
        url = f"/users/{connector._mailbox}/mailFolders"
        response = connector._make_graph_request(url)

        folders = response.get("value", [])
        if folders:
            print_success(f"Mailbox access verified - Found {len(folders)} folders")
            print_info("Available folders:")
            for folder in folders[:10]:  # Show first 10
                print(f"  - {folder.get('displayName')} ({folder.get('totalItemCount', 0)} items)")
            return True
        else:
            print_error("No folders found in mailbox")
            return False

    except Exception as e:
        print_error(f"Mailbox access failed: {e}")
        return False


def test_message_fetch(connector: MicrosoftGraphConnector) -> bool:
    """Test fetching a sample message."""
    print_section("Test 3: Message Retrieval")

    try:
        print_info("Fetching sample messages...")

        # Get Inbox folder
        folder_id = connector._get_folder_id("Inbox")
        if not folder_id:
            print_error("Could not find Inbox folder")
            return False

        print_success(f"Found Inbox folder: {folder_id}")

        # Fetch a few messages
        url = f"/users/{connector._mailbox}/mailFolders/{folder_id}/messages"
        params = {"$top": 3, "$select": "subject,from,receivedDateTime,hasAttachments"}

        response = connector._make_graph_request(url, params=params)
        messages = response.get("value", [])

        if messages:
            print_success(f"Retrieved {len(messages)} sample messages")
            print_info("Sample messages:")
            for msg in messages:
                subject = msg.get("subject", "(No subject)")
                from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "Unknown")
                has_attach = "Yes" if msg.get("hasAttachments") else "No"
                print(f"  - Subject: {subject[:50]}...")
                print(f"    From: {from_addr}")
                print(f"    Attachments: {has_attach}")
            return True
        else:
            print_info("No messages found in Inbox (this is OK if mailbox is empty)")
            return True

    except Exception as e:
        print_error(f"Message fetch failed: {e}")
        return False


def test_attachment_handling(connector: MicrosoftGraphConnector) -> bool:
    """Test attachment downloading."""
    print_section("Test 4: Attachment Handling")

    try:
        print_info("Looking for messages with attachments...")

        # Get Inbox folder
        folder_id = connector._get_folder_id("Inbox")
        if not folder_id:
            print_error("Could not find Inbox folder")
            return False

        # Find a message with attachments
        url = f"/users/{connector._mailbox}/mailFolders/{folder_id}/messages"
        params = {
            "$top": 10,
            "$filter": "hasAttachments eq true",
            "$select": "id,subject,hasAttachments",
        }

        response = connector._make_graph_request(url, params=params)
        messages = response.get("value", [])

        if not messages:
            print_info("No messages with attachments found (skipping test)")
            return True

        # Try to fetch attachments from first message
        message_id = messages[0]["id"]
        subject = messages[0].get("subject", "(No subject)")

        print_info(f"Testing attachment download from: {subject[:50]}...")

        attachments = connector._fetch_attachments(message_id)

        if attachments:
            print_success(f"Successfully downloaded {len(attachments)} attachment(s)")
            for attach in attachments:
                print(f"  - {attach.filename} ({attach.size_bytes} bytes)")
            return True
        else:
            print_info("Message flagged as having attachments but none found")
            return True

    except Exception as e:
        print_error(f"Attachment handling failed: {e}")
        return False


def test_document_conversion(connector: MicrosoftGraphConnector) -> bool:
    """Test converting messages to EvidenceDocument format."""
    print_section("Test 5: Document Conversion")

    try:
        print_info("Testing message to document conversion...")

        # Get one message
        folder_id = connector._get_folder_id("Inbox")
        if not folder_id:
            print_error("Could not find Inbox folder")
            return False

        url = f"/users/{connector._mailbox}/mailFolders/{folder_id}/messages"
        params = {"$top": 1}

        response = connector._make_graph_request(url, params=params)
        messages = response.get("value", [])

        if not messages:
            print_info("No messages found for conversion test (skipping)")
            return True

        message = messages[0]
        document = connector._convert_message_to_document(message)

        print_success("Successfully converted message to EvidenceDocument")
        print_info(f"Document ID: {document.document_id}")
        print_info(f"Subject: {document.subject}")
        print_info(f"Custodian: {document.custodian.email}")
        print_info(f"Metadata fields: {len(document.metadata)}")
        print_info(f"Attachments: {len(document.attachments)}")
        print_info(f"Chain of custody events: {len(document.chain_of_custody)}")

        return True

    except Exception as e:
        print_error(f"Document conversion failed: {e}")
        return False


def run_comprehensive_test(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    mailbox: str,
    include_attachments: bool = True,
) -> bool:
    """Run comprehensive connectivity tests."""

    print("\n" + "="*60)
    print("  Microsoft Graph Connector Test Suite")
    print("="*60)
    print(f"\nTenant ID: {tenant_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'*' * 20}")
    print(f"Target Mailbox: {mailbox}")
    print(f"Include Attachments: {include_attachments}")

    # Create connector
    config = ConnectorConfig(
        type="microsoft_graph",
        name="test_connector",
        enabled=True,
        params={
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "mailbox": mailbox,
            "batch_size": 10,
            "max_messages": 10,
            "include_attachments": include_attachments,
            "folders": ["Inbox"],
        },
    )

    try:
        connector = MicrosoftGraphConnector(config)
    except Exception as e:
        print_error(f"Failed to initialize connector: {e}")
        return False

    # Run tests
    tests = [
        ("Authentication", lambda: test_authentication(connector)),
        ("Mailbox Access", lambda: test_mailbox_access(connector)),
        ("Message Retrieval", lambda: test_message_fetch(connector)),
        ("Attachment Handling", lambda: test_attachment_handling(connector)),
        ("Document Conversion", lambda: test_document_conversion(connector)),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Print summary
    print_section("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Your Microsoft Graph connector is ready to use.\n")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review the output above.\n")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test Microsoft Graph connector connectivity"
    )
    parser.add_argument(
        "--tenant-id",
        help="Azure AD tenant ID (or set AZURE_TENANT_ID env var)",
    )
    parser.add_argument(
        "--client-id",
        help="Azure AD client ID (or set AZURE_CLIENT_ID env var)",
    )
    parser.add_argument(
        "--client-secret",
        help="Azure AD client secret (or set AZURE_CLIENT_SECRET env var)",
    )
    parser.add_argument(
        "--mailbox",
        help="Email address to test",
    )
    parser.add_argument(
        "--no-attachments",
        action="store_true",
        help="Skip attachment download tests",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("ingestion").setLevel(logging.DEBUG)

    # Load environment variables
    load_env_file(args.env_file)

    # Get credentials
    tenant_id = args.tenant_id or os.environ.get("AZURE_TENANT_ID")
    client_id = args.client_id or os.environ.get("AZURE_CLIENT_ID")
    client_secret = args.client_secret or os.environ.get("AZURE_CLIENT_SECRET")
    mailbox = args.mailbox

    # Validate required parameters
    missing = []
    if not tenant_id:
        missing.append("tenant-id (or AZURE_TENANT_ID)")
    if not client_id:
        missing.append("client-id (or AZURE_CLIENT_ID)")
    if not client_secret:
        missing.append("client-secret (or AZURE_CLIENT_SECRET)")
    if not mailbox:
        missing.append("mailbox")

    if missing:
        print_error(f"Missing required parameters: {', '.join(missing)}")
        print("\nPlease provide via command line or set in .env file:")
        print("  AZURE_TENANT_ID=your-tenant-id")
        print("  AZURE_CLIENT_ID=your-client-id")
        print("  AZURE_CLIENT_SECRET=your-client-secret")
        print("\nThen run with: --mailbox user@domain.com")
        sys.exit(1)

    # Run tests
    success = run_comprehensive_test(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        mailbox=mailbox,
        include_attachments=not args.no_attachments,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

