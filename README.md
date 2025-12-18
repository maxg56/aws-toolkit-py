# aws-simple

A clean, simple Python wrapper around AWS services (S3, Textract, Bedrock).

## Features

- **Simple API**: Clean, intuitive interface without exposing Boto3 complexity
- **Environment-based configuration**: No credentials or config in code
- **Structured Textract output**: Transforms AWS Blocks into clean, serializable JSON
- **Type-safe**: Fully typed with Python 3.10+ support
- **Production-ready**: Works with IAM roles, Docker, CI/CD pipelines

## Installation

```bash
pip install aws-simple
```

Or install from source:

```bash
pip install -e .
```

## Configuration

All configuration is done via environment variables:

```bash
# Required
export AWS_REGION=us-east-1
export AWS_S3_BUCKET=my-bucket-name

# Optional
export AWS_PROFILE=my-profile  # For local development
export AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
export AWS_TEXTRACT_REGION=us-east-1
export AWS_BEDROCK_REGION=us-east-1
export AWS_SSL_VERIFY=true  # SSL certificate verification (default: true, set to false to disable)
```

Or use a `.env` file (see [.env.example](.env.example)).

### AWS Credentials

AWS credentials should be configured separately via:
- **IAM Role** (recommended for production/EC2/ECS/Lambda)
- **~/.aws/credentials** file (for local development)
- Environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (not recommended)

## Usage

### S3 Operations

```python
from aws_simple import s3

# Upload file
s3.upload_file("document.pdf", "docs/document.pdf")

# Download file
s3.download_file("docs/document.pdf", "/tmp/document.pdf")

# Read object as bytes
content = s3.read_object("docs/document.pdf")

# List objects
files = s3.list_objects(prefix="docs/")

# Check if object exists
exists = s3.object_exists("docs/document.pdf")
```

### Textract - Document Extraction

```python
from aws_simple import textract
import json

# Extract from local file (with tables)
doc = textract.extract_text_from_file("invoice.pdf")

# Extract from S3 (with tables)
doc = textract.extract_text_from_s3("docs/invoice.pdf")

# Access structured data
print(doc.full_text)  # All text concatenated
print(f"Pages: {len(doc.pages)}")

# Access page details
page = doc.pages[0]
print(f"Lines: {len(page.lines)}")
print(f"Tables: {len(page.tables)}")

# Access lines
for line in page.lines:
    print(f"{line.text} (confidence: {line.confidence})")

# Access tables
for table in page.tables:
    print(f"Table: {table.rows}x{table.columns}")
    print(table.cells)  # 2D matrix of cell values

# Serialize to JSON
doc_json = doc.to_dict()
with open("result.json", "w") as f:
    json.dump(doc_json, f, indent=2)

# Simple text extraction (faster, no tables)
text = textract.extract_text_simple_from_file("document.pdf")
```

### Textract Output Format

The library transforms AWS Textract Blocks into a clean JSON structure:

```json
{
  "pages": [
    {
      "page_number": 1,
      "width": 1.0,
      "height": 1.0,
      "lines": [
        {
          "text": "Invoice #12345",
          "confidence": 99.5,
          "bounding_box": {"top": 0.1, "left": 0.1, "width": 0.2, "height": 0.05}
        }
      ],
      "tables": [
        {
          "rows": 3,
          "columns": 2,
          "cells": [
            ["Item", "Price"],
            ["Product A", "$10"],
            ["Product B", "$20"]
          ],
          "confidence": 98.7
        }
      ],
      "raw_text": "Invoice #12345\n..."
    }
  ],
  "full_text": "All text from all pages concatenated...",
  "metadata": {
    "document_metadata": {...},
    "total_pages": 1
  }
}
```

### Bedrock - LLM Operations

```python
from aws_simple import bedrock

# Simple text generation
response = bedrock.invoke("Explain AWS Lambda in one sentence")
print(response)

# With system prompt and parameters
response = bedrock.invoke(
    prompt="What are the benefits of serverless?",
    system_prompt="You are an AWS solutions architect.",
    temperature=0.7,
    max_tokens=500
)

# Request JSON output
prompt = """
List 3 AWS services with their use cases.
Format: {"services": [{"name": "...", "use_case": "..."}]}
"""
data = bedrock.invoke_json(prompt)
print(data["services"])

# Use different model
response = bedrock.invoke(
    "Summarize this text...",
    model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"
)
```

### Combined Workflow

```python
from aws_simple import s3, textract, bedrock
import json

# 1. Upload document
s3.upload_file("invoice.pdf", "invoices/2024/inv_001.pdf")

# 2. Extract content
doc = textract.extract_text_from_s3("invoices/2024/inv_001.pdf")

# 3. Analyze with LLM
prompt = f"""
Extract key information from this invoice:

{doc.full_text}

Return JSON with: invoice_number, date, total, vendor
"""

invoice_data = bedrock.invoke_json(prompt)
print(json.dumps(invoice_data, indent=2))
```

## Architecture

```
aws-simple/
├── config.py           # Environment variable configuration
├── exceptions.py       # Custom exceptions
├── _clients.py         # AWS client factory (internal)
├── s3.py              # S3 operations
├── textract.py        # Textract operations
├── bedrock.py         # Bedrock operations
├── models/            # Data models
│   └── textract.py    # TextractDocument, TextractPage, etc.
└── _parsers/          # Internal parsers
    └── textract_parser.py  # Transforms Blocks → JSON
```

## Design Principles

1. **No Boto3 in public API**: AWS implementation details are hidden
2. **Environment-based config**: All configuration via env vars
3. **Clean output formats**: No raw AWS responses exposed
4. **Type safety**: Full type hints for better IDE support
5. **Simple error handling**: Custom exceptions for each service
6. **Production-ready**: Compatible with Docker, IAM roles, CI/CD

## Exceptions

```python
from aws_simple import (
    AWSSimpleError,          # Base exception
    ConfigurationError,      # Missing/invalid configuration
    S3Error,                 # S3 operation failures
    TextractError,          # Textract operation failures
    BedrockError,           # Bedrock operation failures
    ClientInitializationError  # AWS client init failures
)

try:
    doc = textract.extract_text_from_s3("missing.pdf")
except TextractError as e:
    print(f"Extraction failed: {e}")
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

## Requirements

- Python ≥ 3.10
- boto3 ≥ 1.34.0
- python-dotenv ≥ 1.0.0

## License

MIT

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/maxg56/aws-toolkit-py).
