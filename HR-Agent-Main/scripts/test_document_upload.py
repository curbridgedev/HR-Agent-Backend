"""
Test document upload endpoint.
"""

import asyncio
import httpx
from pathlib import Path


async def test_upload():
    """Test document upload with a sample file."""

    # Create a sample text file for testing
    test_content = """
# Compaytence Payment Processing Guide

## Introduction
This guide covers the payment processing capabilities of Compaytence.

## Supported Payment Methods
1. Credit Cards (Visa, Mastercard, Amex)
2. Bank Transfers
3. Digital Wallets (PayPal, Apple Pay)

## Processing Flow
When a payment is initiated:
1. Payment validation
2. Fraud detection
3. Authorization request
4. Settlement
5. Confirmation

## Refund Policy
Refunds are processed within 5-7 business days.
All refunds require manager approval.

## Support
For payment issues, contact: support@compaytence.com
"""

    # Create temporary test file
    test_file = Path("test_document.md")
    test_file.write_text(test_content)

    try:
        print("Testing document upload...")
        print(f"File: {test_file.name} ({test_file.stat().st_size} bytes)\n")

        # Upload file
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(test_file, "rb") as f:
                files = {"file": (test_file.name, f, "text/markdown")}
                data = {
                    "title": "Payment Processing Guide",
                    "source": "admin_upload",
                }

                response = await client.post(
                    "http://localhost:8000/api/v1/documents/upload",
                    files=files,
                    data=data,
                )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}\n")

        if response.status_code == 201:
            print("✅ Upload successful!")
            result = response.json()
            print(f"Document ID: {result['document_id']}")
            print(f"Chunks created: Check database for chunks")
        else:
            print(f"❌ Upload failed: {response.text}")

    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()
            print(f"\nCleaned up test file: {test_file}")


if __name__ == "__main__":
    asyncio.run(test_upload())
