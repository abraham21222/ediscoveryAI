#!/usr/bin/env python3
"""Test script for file analyzer functionality."""

import sys
from pathlib import Path
from ingestion.file_analyzer import FileAnalyzer, FileCategory, DataQuality

def test_pdf_detection():
    """Test PDF file detection from bytes."""
    # Create a minimal valid PDF
    pdf_data = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\ntrailer\n<<\n>>\n%%EOF\n'
    
    analyzer = FileAnalyzer()
    analysis = analyzer.analyze_bytes('test.pdf', pdf_data)
    
    print(f"✓ PDF Detection:")
    print(f"  - Category: {analysis.category.value}")
    print(f"  - Quality: {analysis.quality.value}")
    print(f"  - MIME: {analysis.mime_type}")
    print(f"  - Detected MIME: {analysis.detected_mime}")
    print(f"  - Processable: {analysis.is_processable}")
    print()
    
    assert analysis.category == FileCategory.DOCUMENT
    assert analysis.detected_mime == 'application/pdf'
    return True

def test_image_detection():
    """Test image file detection."""
    # JPEG magic bytes
    jpeg_data = b'\xff\xd8\xff\xe0' + b'\x00' * 1000 + b'\xff\xd9'
    
    analyzer = FileAnalyzer()
    analysis = analyzer.analyze_bytes('photo.jpg', jpeg_data)
    
    print(f"✓ JPEG Detection:")
    print(f"  - Category: {analysis.category.value}")
    print(f"  - Quality: {analysis.quality.value}")
    print(f"  - Detected MIME: {analysis.detected_mime}")
    print()
    
    assert analysis.category == FileCategory.IMAGE
    assert analysis.detected_mime == 'image/jpeg'
    return True

def test_corrupted_file():
    """Test corrupted file detection."""
    # Truncated JPEG (missing EOI marker)
    corrupted_jpeg = b'\xff\xd8\xff\xe0' + b'\x00' * 1000  # Missing \xff\xd9
    
    analyzer = FileAnalyzer()
    analysis = analyzer.analyze_bytes('broken.jpg', corrupted_jpeg)
    
    print(f"✓ Corrupted File Detection:")
    print(f"  - Quality: {analysis.quality.value}")
    print(f"  - Details: {analysis.quality_details}")
    print(f"  - Processable: {analysis.is_processable}")
    print()
    
    assert analysis.quality == DataQuality.CORRUPTED
    return True

def test_encrypted_pdf():
    """Test encrypted PDF detection."""
    # PDF with encryption marker
    encrypted_pdf = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Encrypt 2 0 R\n>>\nendobj\n%%EOF\n'
    
    analyzer = FileAnalyzer()
    analysis = analyzer.analyze_bytes('encrypted.pdf', encrypted_pdf)
    
    print(f"✓ Encrypted File Detection:")
    print(f"  - Quality: {analysis.quality.value}")
    print(f"  - Details: {analysis.quality_details}")
    print()
    
    assert analysis.quality == DataQuality.ENCRYPTED
    return True

def test_extension_mismatch():
    """Test MIME type mismatch detection."""
    # ZIP file masquerading as PDF
    zip_data = b'PK\x03\x04' + b'\x00' * 100
    
    analyzer = FileAnalyzer()
    analysis = analyzer.analyze_bytes('fake.pdf', zip_data)
    
    print(f"✓ Extension Mismatch Detection:")
    print(f"  - Declared MIME: {analysis.mime_type}")
    print(f"  - Detected MIME: {analysis.detected_mime}")
    print(f"  - Quality: {analysis.quality.value}")
    print(f"  - Details: {analysis.quality_details}")
    print()
    
    assert analysis.quality == DataQuality.INVALID_FORMAT
    return True

def test_hashing():
    """Test file hashing."""
    test_data = b'Hello, World!'
    
    analyzer = FileAnalyzer()
    analysis = analyzer.analyze_bytes('test.txt', test_data)
    
    print(f"✓ Hashing:")
    print(f"  - MD5: {analysis.md5_hash}")
    print(f"  - SHA256: {analysis.sha256_hash}")
    print()
    
    assert len(analysis.md5_hash) == 32
    assert len(analysis.sha256_hash) == 64
    return True

def main():
    """Run all tests."""
    print("="*60)
    print("File Analyzer Test Suite")
    print("="*60)
    print()
    
    tests = [
        ("PDF Detection", test_pdf_detection),
        ("Image Detection", test_image_detection),
        ("Corrupted File Detection", test_corrupted_file),
        ("Encrypted File Detection", test_encrypted_pdf),
        ("Extension Mismatch Detection", test_extension_mismatch),
        ("File Hashing", test_hashing),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"✗ {test_name} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
            failed += 1
    
    print("="*60)
    print(f"Results: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"         {failed} tests failed")
        sys.exit(1)
    else:
        print("✓ All tests passed!")
        sys.exit(0)

if __name__ == '__main__':
    main()

