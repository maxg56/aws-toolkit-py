# aws-simple

A clean, simple Python wrapper around AWS services (S3, Textract, Bedrock).

## Features

- **Simple API**: Clean, intuitive interface without exposing Boto3 complexity
- **Environment-based configuration**: No credentials or config in code
- **Custom endpoints**: Works against LocalStack, MinIO or any S3-compatible stack
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

Configuration comes from environment variables (or from code — see
[Programmatic configuration](#programmatic-configuration)):

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

# Optional: custom endpoints (LocalStack, MinIO, any S3-compatible stack)
export AWS_ENDPOINT_URL=http://localhost:4566        # applies to every service
export AWS_S3_ENDPOINT_URL=http://localhost:9000     # per-service override
export AWS_TEXTRACT_ENDPOINT_URL=http://localhost:4566
export AWS_BEDROCK_ENDPOINT_URL=http://localhost:4566

# Optional: explicit credentials (see below)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...   # only for temporary credentials
```

Or use a `.env` file (see [.env.example](.env.example)).

### Custom endpoints (LocalStack / MinIO)

Set `AWS_ENDPOINT_URL` to point every client at an AWS-compatible stack, or a
per-service variable (`AWS_S3_ENDPOINT_URL`, `AWS_TEXTRACT_ENDPOINT_URL`,
`AWS_BEDROCK_ENDPOINT_URL`) to override it for a single service. Each
per-service variable falls back to `AWS_ENDPOINT_URL`, and when none is set the
regular AWS endpoints are used.

```bash
# Everything against LocalStack, S3 against a local MinIO
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_S3_ENDPOINT_URL=http://localhost:9000
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

If the local stack serves a self-signed certificate, `AWS_SSL_VERIFY=false`
disables verification. Never do that against a real AWS endpoint.

### AWS Credentials

By default credentials are resolved by the standard boto3 chain, which is the
recommended setup:
- **IAM Role** (recommended for production/EC2/ECS/Lambda)
- **~/.aws/credentials** file, optionally selected with `AWS_PROFILE`
- The ambient environment

They can also be provided explicitly, which is what local stacks and
applications juggling per-tenant or per-request credentials need:

| Variable | Notes |
|---|---|
| `AWS_ACCESS_KEY_ID` | optional |
| `AWS_SECRET_ACCESS_KEY` | optional |
| `AWS_SESSION_TOKEN` | optional, for temporary credentials |

`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are only handed to boto3 when
**both** are set — a partial pair is ignored, so it can never silently break the
default credential chain. `AWS_SESSION_TOKEN` is only sent alongside a complete
pair.

Credential values are never logged, never included in a `Config` repr, and are
scrubbed out of `ClientInitializationError` messages, so a boto3 error quoting a
key does not propagate it.

## Programmatic configuration

Everything above can also be set from code, which is what an application that
reads its settings from a config file, Parameter Store or CLI flags needs:

```python
from aws_simple import configure

configure(
    region="eu-west-3",
    bucket="my-bucket",
    endpoint_url="http://localhost:4566",
)
```

All arguments are optional and keyword-only. Arguments left out are untouched,
so successive calls accumulate.

### Precedence

From strongest to weakest:

1. **`configure()`** — values set from code
2. **Environment variables** — `AWS_REGION`, `AWS_S3_BUCKET`, …
3. **`.env` file** — loaded at import time, and only for variables the
   environment does not already define
4. **Built-in defaults** — e.g. `us-east-1` for the region

A setting you never pass to `configure()` keeps coming from the environment, so
you can override just the region and let everything else resolve as usual.

### Settings

| `configure()` argument | Overrides |
|---|---|
| `region` | `AWS_REGION` |
| `profile` | `AWS_PROFILE` |
| `bucket` | `AWS_S3_BUCKET` |
| `endpoint_url` | `AWS_ENDPOINT_URL` |
| `s3_endpoint_url` | `AWS_S3_ENDPOINT_URL` |
| `textract_region` | `AWS_TEXTRACT_REGION` |
| `textract_endpoint_url` | `AWS_TEXTRACT_ENDPOINT_URL` |
| `bedrock_region` | `AWS_BEDROCK_REGION` |
| `bedrock_endpoint_url` | `AWS_BEDROCK_ENDPOINT_URL` |
| `bedrock_model_id` | `AWS_BEDROCK_MODEL_ID` |
| `aws_access_key_id` | `AWS_ACCESS_KEY_ID` |
| `aws_secret_access_key` | `AWS_SECRET_ACCESS_KEY` |
| `aws_session_token` | `AWS_SESSION_TOKEN` |

Credentials passed to `configure()` follow the same rules as their environment
counterparts: a partial pair is ignored, and the values are never logged, never
part of a `Config` repr, and are scrubbed out of client initialization errors.

### Reconfiguring at runtime

AWS clients are built once and cached. **Every configuration change through
`configure()` invalidates that cache**, so it applies to the next call even when
a client was already built:

```python
from aws_simple import configure, s3

s3.list_objects("a/")              # client built for the current region
configure(region="eu-west-3")      # cached clients dropped
s3.list_objects("b/")              # rebuilt: hits eu-west-3
```

Mutating `os.environ` after the first call does **not** do this — the already
built client keeps its old settings. Use `configure()` instead.

`reset_configuration()` drops every value set from code, so configuration falls
back to the environment (this also invalidates the cache):

```python
from aws_simple import reset_configuration

reset_configuration()
```

### Per-call region overrides

Passing a `region` to an individual service call (`s3.list_objects(..., region=...)`)
is **out of scope**: clients are cached per service, not per region, and a
per-call region would still leave the bucket, endpoint and credentials on the
global configuration. `configure()` is the supported way to change region — call
it when your application switches region, or once per region-scoped unit of
work.

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

# Write bytes (or a str, encoded as UTF-8) directly, no temp file needed
s3.put_object("docs/report.json", '{"status": "ok"}')
s3.put_object("docs/report.bin", b"\x00\x01\x02")

# Delete an object
s3.delete_object("docs/document.pdf")

# Copy an object (within a bucket, or across buckets)
s3.copy_object("inbox/document.pdf", "archive/document.pdf")
s3.copy_object(
    "inbox/document.pdf",
    "archive/document.pdf",
    source_bucket="incoming",
    dest_bucket="processed",
)

# List objects
files = s3.list_objects(prefix="docs/")

# Check if object exists
exists = s3.object_exists("docs/document.pdf")
```

All S3 functions take the bucket from the `AWS_S3_BUCKET` environment variable
unless one is passed explicitly, and raise `S3Error` (chaining the underlying
`ClientError`) with a message naming the `s3://bucket/key` involved.

### Textract - Document Extraction

> **⚠️ Current limitation: 1 page per request**
>
> `extract_text_from_file`, `extract_text_from_s3`, `extract_text_simple_from_file`, and
> `extract_text_simple_from_s3` use the **synchronous** Textract APIs
> (`analyze_document` / `detect_document_text` with `Document={"Bytes": ...}` or
> `Document={"S3Object": ...}`). These APIs reliably process only an **image** or a
> **single-page PDF**. For multi-page PDFs, only the first page is reliable (AWS does not
> guarantee behavior for subsequent pages).
>
> Supporting multi-page PDFs requires switching to the **asynchronous** Textract APIs
> (`StartDocumentAnalysis`/`StartDocumentTextDetection` via S3) or splitting the document
> client-side before extraction — see
> [#11](https://github.com/maxg56/aws-toolkit-py/issues/11).

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

> **Note:** Supports Anthropic Claude, Amazon Titan, Meta Llama and Mistral
> models, selected automatically from the `model_id`
> (e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0`, `amazon.titan-text-express-v1`,
> `meta.llama3-8b-instruct-v1:0`, `mistral.mistral-7b-instruct-v0:2`).
> Calling `invoke()`/`invoke_json()` with a model ID from another family
> raises `BedrockError`.

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
├── config.py           # Configuration: env vars, .env and configure()
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
2. **Environment-based config**: Env vars by default, overridable from code
   with `configure()`
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

## Integration tests (LocalStack)

The default `pytest` run is unit-only: every test mocks boto3, so it is fast
and needs no network. Those tests assert *what the library calls*, never that
the call works — a wrong parameter name or a bad pagination token would pass
them all.

The `tests/integration/` suite closes that gap by running the same S3
functions against a real S3 implementation over HTTP. It is marked
`integration` and deselected by default, so it never slows down or breaks an
ordinary test run.

```bash
# Unit tests only (the default; no endpoint needed)
pytest

# Start an S3 endpoint, then run the integration suite
docker run --rm -d -p 4566:4566 -e SERVICES=s3 localstack/localstack:3
pytest -m integration          # or: make test-integration
```

LocalStack is driven purely through the library's public configuration —
`AWS_ENDPOINT_URL` and the credential variables — so the suite exercises the
same code path as a real deployment. Nothing patches library internals.

**What it covers:** the `list_objects` `ContinuationToken` pagination path
past S3's 1000-key page size, `max_keys` trimming across that boundary,
`object_exists` on a missing key (the `HeadObject` 404 branch),
`put_object` / `read_object` round trips including UTF-8 and empty bodies,
`upload_file` / `download_file`, `delete_object` idempotence, and
`copy_object` within and across buckets — including keys that need URL
encoding, where a real endpoint rejects what a mock accepts.

Scoped to S3 on purpose: LocalStack's free tier does not meaningfully emulate
Textract or Bedrock.

Environment variables the suite honours:

| Variable | Default | Purpose |
|---|---|---|
| `AWS_ENDPOINT_URL` | `http://127.0.0.1:4566` | Endpoint to test against; any S3-compatible endpoint works |
| `AWS_SIMPLE_INTEGRATION_TIMEOUT` | `60` | Seconds to wait for the endpoint to answer before giving up |
| `AWS_SIMPLE_INTEGRATION_REQUIRED` | unset | When truthy, an unreachable endpoint fails instead of skipping |

Without a reachable endpoint the suite skips itself, so `pytest -m
integration` is harmless on a machine without LocalStack. CI sets
`AWS_SIMPLE_INTEGRATION_REQUIRED=1` in its own standalone
`Integration Tests (LocalStack)` job, so a job whose container never came up
fails loudly instead of passing green with everything skipped.

## Requirements

- Python ≥ 3.10
- boto3 ≥ 1.34.0
- python-dotenv ≥ 1.0.0

## License

Apache-2.0 — see the [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/maxg56/aws-toolkit-py).
