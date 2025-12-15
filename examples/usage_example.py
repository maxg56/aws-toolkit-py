"""
Example usage of aws-simple library.

Make sure to configure environment variables before running:
    export AWS_REGION=us-east-1
    export AWS_S3_BUCKET=my-bucket
"""

import json

from aws_simple import bedrock, s3, textract


def main() -> None:
    """Demonstrate aws-simple library usage."""

    print("=" * 60)
    print("AWS Simple Library - Usage Examples")
    print("=" * 60)

    # ========================================
    # S3 Examples
    # ========================================
    print("\n[S3 Operations]")

    # Upload a file
    print("Uploading file to S3...")
    s3.upload_file("examples/sample_document.pdf", "docs/sample.pdf")
    print("✓ Uploaded to s3://bucket/docs/sample.pdf")

    # List objects
    print("\nListing objects with prefix 'docs/'...")
    objects = s3.list_objects(prefix="docs/")
    for obj_key in objects:
        print(f"  - {obj_key}")

    # Check if object exists
    exists = s3.object_exists("docs/sample.pdf")
    print(f"\nObject exists: {exists}")

    # Read object as bytes
    content = s3.read_object("docs/sample.pdf")
    print(f"Object size: {len(content)} bytes")

    # Download file
    s3.download_file("docs/sample.pdf", "/tmp/downloaded_sample.pdf")
    print("✓ Downloaded to /tmp/downloaded_sample.pdf")

    # ========================================
    # Textract Examples
    # ========================================
    print("\n" + "=" * 60)
    print("[Textract Operations]")

    # Extract from local file
    print("\nExtracting text from local PDF...")
    doc = textract.extract_text_from_file("examples/sample_document.pdf")

    print(f"\nDocument metadata:")
    print(f"  - Total pages: {len(doc.pages)}")
    print(f"  - Total text length: {len(doc.full_text)} characters")

    # Access structured data
    print(f"\n First page info:")
    if doc.pages:
        page = doc.pages[0]
        print(f"  - Page number: {page.page_number}")
        print(f"  - Dimensions: {page.width} x {page.height}")
        print(f"  - Lines detected: {len(page.lines)}")
        print(f"  - Tables detected: {len(page.tables)}")

        # Show first 3 lines
        print(f"\n  First 3 lines:")
        for line in page.lines[:3]:
            print(f"    - {line.text} (confidence: {line.confidence:.1f}%)")

        # Show table structure if exists
        if page.tables:
            table = page.tables[0]
            print(f"\n  First table: {table.rows} rows x {table.columns} columns")
            print(f"    First row: {table.cells[0]}")

    # Extract from S3
    print("\nExtracting text from S3 document...")
    doc_s3 = textract.extract_text_from_s3("docs/sample.pdf")
    print(f"Extracted {len(doc_s3.full_text)} characters from S3 document")

    # Simple text-only extraction (faster)
    print("\nSimple text extraction (no tables)...")
    simple_text = textract.extract_text_simple_from_file("examples/sample_document.pdf")
    print(f"Extracted text preview: {simple_text[:200]}...")

    # Serialize to JSON
    print("\nSerializing document to JSON...")
    doc_json = doc.to_dict()
    print(f"JSON keys: {list(doc_json.keys())}")
    # Save to file
    with open("/tmp/textract_result.json", "w") as f:
        json.dump(doc_json, f, indent=2)
    print("✓ Saved to /tmp/textract_result.json")

    # ========================================
    # Bedrock Examples
    # ========================================
    print("\n" + "=" * 60)
    print("[Bedrock Operations]")

    # Simple text generation
    print("\nGenerating text with Bedrock...")
    prompt = "Explain what AWS Textract does in one sentence."
    response = bedrock.invoke(prompt)
    print(f"Response: {response}")

    # Generate with system prompt
    print("\nGenerating with system prompt...")
    response = bedrock.invoke(
        prompt="What are the main benefits?",
        system_prompt="You are an AWS solutions architect. Be concise.",
        temperature=0.7,
    )
    print(f"Response: {response}")

    # JSON output
    print("\nRequesting JSON response...")
    json_prompt = """
    List 3 AWS services and their main use case.
    Return as JSON with format: {"services": [{"name": "...", "use_case": "..."}]}
    """
    json_response = bedrock.invoke_json(json_prompt)
    print(f"JSON response:")
    print(json.dumps(json_response, indent=2))

    # ========================================
    # Combined workflow
    # ========================================
    print("\n" + "=" * 60)
    print("[Combined Workflow Example]")

    # 1. Upload document
    print("\n1. Uploading document to S3...")
    s3.upload_file("examples/invoice.pdf", "invoices/2024/invoice_001.pdf")

    # 2. Extract content
    print("2. Extracting content with Textract...")
    invoice_doc = textract.extract_text_from_s3("invoices/2024/invoice_001.pdf")

    # 3. Analyze with Bedrock
    print("3. Analyzing with Bedrock LLM...")
    analysis_prompt = f"""
    Analyze this invoice and extract key information as JSON:

    {invoice_doc.full_text}

    Return JSON with: invoice_number, date, total_amount, vendor
    """
    invoice_data = bedrock.invoke_json(analysis_prompt)
    print("Extracted invoice data:")
    print(json.dumps(invoice_data, indent=2))

    print("\n" + "=" * 60)
    print("✓ All examples completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
