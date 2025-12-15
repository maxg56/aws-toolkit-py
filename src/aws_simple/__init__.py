"""
aws-simple: A clean, simple wrapper around AWS services.

Simplifies usage of AWS S3, Textract, and Bedrock through a clean API.
Configuration is done entirely via environment variables.

Example usage:
    from aws_simple import s3, textract, bedrock

    # S3 operations
    s3.upload_file("doc.pdf", "docs/doc.pdf")
    content = s3.read_object("docs/doc.pdf")

    # Textract extraction
    doc = textract.extract_text_from_s3("docs/doc.pdf")
    print(doc.full_text)
    print(doc.to_dict())  # Serialize to JSON

    # Bedrock LLM
    summary = bedrock.invoke("Summarize this document")
    data = bedrock.invoke_json("Extract key points as JSON")
"""

from . import bedrock, s3, textract
from .exceptions import (
    AWSSimpleError,
    BedrockError,
    ClientInitializationError,
    ConfigurationError,
    S3Error,
    TextractError,
)
from .models import TextractDocument, TextractLine, TextractPage, TextractTable

__version__ = "0.1.0"

__all__ = [
    # Modules
    "s3",
    "textract",
    "bedrock",
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
