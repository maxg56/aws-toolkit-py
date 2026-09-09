# aws-simple

A clean, simple Python wrapper around AWS services (S3, Textract, Bedrock).

## Features

- **Simple API**: Clean, intuitive interface without exposing Boto3 complexity
- **Environment-based configuration**: No credentials or config in code, with a `configure()` escape hatch for code-driven settings
- **Custom endpoints**: Works against LocalStack, MinIO or any S3-compatible stack
- **Tuned for real workloads**: Configurable retries/timeouts (standard retry mode, throttling-aware defaults)
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

Configuration can come from environment variables, a `.env` file, or the
[`configure()`](#programmatic-configuration) function — see
[Configuration precedence](#configuration-precedence) below.

```bash
# Required
export AWS_REGION=us-east-1
export AWS_S3_BUCKET=my-bucket-name

# Optional
export AWS_PROFILE=my-profile  # For local development
export AWS_BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
export AWS_TEXTRACT_REGION=us-east-1
export AWS_BEDROCK_REGION=us-east-1

# Optional: custom endpoints (LocalStack, MinIO, any S3-compatible stack)
export AWS_ENDPOINT_URL=http://localhost:4566        # applies to every service
export AWS_S3_ENDPOINT_URL=http://localhost:9000     # per-service override
export AWS_TEXTRACT_ENDPOINT_URL=http://localhost:4566
export AWS_BEDROCK_ENDPOINT_URL=http://localhost:4566

# Optional: explicit credentials (see below)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...   # only for temporary credentials

# Optional: retry / timeout tuning, see "Retries and timeouts" below
export AWS_MAX_ATTEMPTS=3
export AWS_RETRY_MODE=standard
export AWS_CONNECT_TIMEOUT=10
export AWS_READ_TIMEOUT=60
```

Or use a `.env` file (see [.env.example](.env.example)).

### Configuration precedence

For any given setting: a `configure()` call wins, then the specific
environment variable, then the variable's documented default. A `.env` file
is just a way to populate environment variables (via `python-dotenv`) before
the process starts, so it sits at the same precedence level as `export`ing
the variable yourself.

### Programmatic configuration

Reach for `configure()` when settings come from your own config file,
Parameter Store, CLI flags, or anywhere else that isn't an environment
variable — or simply to override one setting from code without touching
`os.environ`:

```python
from aws_simple import configure

configure(region="eu-west-3", bucket="my-bucket", endpoint_url="http://localhost:4566")
```

Passing a value overrides it; omitting a parameter (leaving it `None`) keeps
whatever was configured before, whether that came from an earlier
`configure()` call or an environment variable. Calling `configure()` also
resets every cached AWS client, so the very next S3/Textract/Bedrock call is
built from the new settings — without it, a client already built for the old
region would otherwise keep being reused silently.

`configure()` accepts: `region`, `profile`, `endpoint_url`, `bucket`,
`s3_endpoint_url`, `textract_region`, `textract_endpoint_url`,
`bedrock_region`, `bedrock_endpoint_url`, `bedrock_model_id`,
`access_key_id`, `secret_access_key`, `session_token`, `max_attempts`,
`retry_mode`, `connect_timeout`, `read_timeout`.

There is no per-call region/bucket override on `s3`/`textract`/`bedrock`
functions themselves — for multi-region or multi-tenant use, call
`configure()` again before the calls that need the other settings.

### Retries and timeouts

Every client is built with a `botocore.config.Config` derived from these
variables:

| Setting | Env var | Default |
|---|---|---|
| Max retry attempts | `AWS_MAX_ATTEMPTS` | 3 |
| Retry mode | `AWS_RETRY_MODE` | `standard` |
| Connect timeout (s) | `AWS_CONNECT_TIMEOUT` | 10 |
| Read timeout (s) | `AWS_READ_TIMEOUT` | 60 |

This is a **behaviour change from botocore's own defaults** (`legacy` retry
mode, 5 attempts, 60s connect/read timeouts): `standard` mode retries a
broader, more correct set of errors (including throttling), which matters a
lot for Bedrock (`ThrottlingException` under load) and Textract (bursty
synchronous calls). If you were relying on `legacy` mode's narrower retry
behaviour, set `AWS_RETRY_MODE=legacy` explicitly.

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

If the local stack serves a self-signed certificate, see "Development only:
disabling SSL verification" below — verification can only be turned off for
a custom endpoint like this one, never for a real AWS endpoint.

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

## Development only: disabling SSL verification

`AWS_INSECURE_DISABLE_SSL_VERIFY=true` disables TLS certificate verification
— only ever do this against a local stack with a self-signed certificate
(LocalStack, MinIO), never against real AWS:

```bash
export AWS_ENDPOINT_URL=https://localhost:4566
export AWS_INSECURE_DISABLE_SSL_VERIFY=true
```

This cannot be used to weaken a real connection to AWS: if no custom
`endpoint_url` is configured, or the configured one resolves to an
`amazonaws.com` host, the library raises `ConfigurationError` instead of
silently building an insecure client — a variable set for local development
and later inherited into staging or production (a shared `.env`, a Docker
Compose base file, a CI export) cannot end up disabling verification against
production AWS traffic without you noticing. When it *is* honoured for a
genuine custom endpoint, a `UserWarning` naming that endpoint is emitted the
first time a client is built with verification off.

The older `AWS_SSL_VERIFY` variable still works for one more minor version —
note that its polarity is the opposite of the new one (`AWS_SSL_VERIFY=false`
disabled verification) — and emits a `DeprecationWarning` when used.

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

# Run unit tests (fast, mocked boto3 — this is what `pytest` runs by default)
pytest

# Type checking
mypy src/

# Linting
ruff check src/
```

### Integration tests (LocalStack)

The unit suite mocks every boto3 call, which is fast but only proves *what*
we call, never that S3 actually accepts the request as built (pagination
tokens, `MaxKeys`, the 404 branch of `head_object`, ...). `tests/integration/`
covers that against a real LocalStack instance and is excluded from the
default `pytest` run (`-m "not integration"` in `pyproject.toml`):

```bash
# Start LocalStack (S3 only) in the background
docker run -d --rm -p 4566:4566 -e SERVICES=s3 localstack/localstack:3

# Run just the integration suite against it
pytest -m integration --no-cov
```

It targets `AWS_ENDPOINT_URL` (default `http://localhost:4566`) with
`AWS_ACCESS_KEY_ID=test` / `AWS_SECRET_ACCESS_KEY=test`, and every test skips
cleanly if nothing is listening there. CI runs it in its own job against a
LocalStack service container; a failure there is reported but does not block
the rest of CI, since it is as likely to be container startup flakiness as an
actual regression.

## Requirements

- Python ≥ 3.10
- boto3 ≥ 1.34.0
- python-dotenv ≥ 1.0.0

## License

Apache-2.0 — see the [LICENSE](LICENSE) file for details.

## Support

For issues and feature requests, please visit the [GitHub repository](https://github.com/maxg56/aws-toolkit-py).
