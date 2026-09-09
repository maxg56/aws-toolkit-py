"""
aws-simple: A clean, simple wrapper around AWS services.

Simplifies usage of AWS S3, Textract, and Bedrock through a clean API.
Configuration comes from environment variables (or a .env file) and can be
overridden from code with configure().

Example usage:
    from aws_simple import configure, s3, textract, bedrock

    # Optional: configure from code (overrides the environment)
    configure(region="eu-west-3", bucket="my-bucket")

    # S3 operations
    s3.upload_file("doc.pdf", "docs/doc.pdf")
    content = s3.read_object("docs/doc.pdf")
    s3.put_object("docs/note.txt", "written from memory")

    # Textract extraction
    doc = textract.extract_text_from_s3("docs/doc.pdf")
    print(doc.full_text)
    print(doc.to_dict())  # Serialize to JSON

    # Bedrock LLM
    summary = bedrock.invoke("Summarize this document")
    data = bedrock.invoke_json("Extract key points as JSON")

    # Archive the document once it has been processed
    s3.copy_object("docs/doc.pdf", "archive/doc.pdf")
    s3.delete_object("docs/doc.pdf")
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from . import bedrock, s3, textract
from .config import configure, reset_configuration
from .exceptions import (
    AWSSimpleError,
    BedrockError,
    ClientInitializationError,
    ConfigurationError,
    S3Error,
    TextractError,
)
from .models import TextractDocument, TextractLine, TextractPage, TextractTable

try:
    __version__ = _version("aws-simple")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"  # pragma: no cover - package not installed (e.g. source tree)

__all__ = [
    # Modules
    "s3",
    "textract",
    "bedrock",
    # Configuration
    "configure",
    "reset_configuration",
    # Exceptions
    "AWSSimpleError",
    "BedrockError",
    "ClientInitializationError",
    "ConfigurationError",
    "S3Error",
    "TextractError",
    # Models
    "TextractDocument",
    "TextractLine",
    "TextractPage",
    "TextractTable",
]
