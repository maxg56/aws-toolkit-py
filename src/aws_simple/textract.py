"""Textract operations module."""

from pathlib import Path

from botocore.exceptions import ClientError

from ._clients import AWSClients
from ._parsers.textract_parser import TextractParser
from .config import config
from .exceptions import TextractError
from .models.textract import TextractDocument


def extract_text_from_file(local_path: str | Path) -> TextractDocument:
    """
    Extract text and tables from a local file using Textract.

    Supports: PDF, PNG, JPEG, TIFF (max 5MB for synchronous detection)

    Args:
        local_path: Path to local document file

    Returns:
        TextractDocument with structured content

    Raises:
        TextractError: If extraction fails
    """
    local_path = Path(local_path)

    if not local_path.exists():
        raise TextractError(f"Local file not found: {local_path}")

    try:
        with open(local_path, "rb") as f:
            document_bytes = f.read()

        client = AWSClients.get_textract_client()

        # Use detect_document_text for simple text extraction
        # Use analyze_document for tables and forms
        response = client.analyze_document(
            Document={"Bytes": document_bytes},
            FeatureTypes=["TABLES"],  # Enable table detection
        )

        return TextractParser.parse_response(response)

    except ClientError as e:
        raise TextractError(f"Failed to extract text from {local_path}: {e}") from e
    except Exception as e:
        raise TextractError(f"Unexpected error extracting text from {local_path}: {e}") from e


def extract_text_from_s3(
    s3_key: str,
    bucket: str | None = None,
) -> TextractDocument:
    """
    Extract text and tables from a document stored in S3 using Textract.

    Args:
        s3_key: S3 object key
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Returns:
        TextractDocument with structured content

    Raises:
        TextractError: If extraction fails
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_textract_client()

        response = client.analyze_document(
            Document={
                "S3Object": {
                    "Bucket": bucket,
                    "Name": s3_key,
                }
            },
            FeatureTypes=["TABLES"],  # Enable table detection
        )

        return TextractParser.parse_response(response)

    except ClientError as e:
        raise TextractError(f"Failed to extract text from s3://{bucket}/{s3_key}: {e}") from e
    except Exception as e:
        raise TextractError(
            f"Unexpected error extracting text from s3://{bucket}/{s3_key}: {e}"
        ) from e


def extract_text_simple_from_file(local_path: str | Path) -> str:
    """
    Extract only text (no tables) from a local file - faster operation.

    Args:
        local_path: Path to local document file

    Returns:
        Extracted text as string

    Raises:
        TextractError: If extraction fails
    """
    local_path = Path(local_path)

    if not local_path.exists():
        raise TextractError(f"Local file not found: {local_path}")

    try:
        with open(local_path, "rb") as f:
            document_bytes = f.read()

        client = AWSClients.get_textract_client()

        response = client.detect_document_text(
            Document={"Bytes": document_bytes},
        )

        # Extract just text from blocks
        blocks = response.get("Blocks", [])
        lines = [block["Text"] for block in blocks if block.get("BlockType") == "LINE"]

        return "\n".join(lines)

    except ClientError as e:
        raise TextractError(f"Failed to extract text from {local_path}: {e}") from e
    except Exception as e:
        raise TextractError(f"Unexpected error extracting text from {local_path}: {e}") from e


def extract_text_simple_from_s3(
    s3_key: str,
    bucket: str | None = None,
) -> str:
    """
    Extract only text (no tables) from S3 document - faster operation.

    Args:
        s3_key: S3 object key
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Returns:
        Extracted text as string

    Raises:
        TextractError: If extraction fails
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_textract_client()

        response = client.detect_document_text(
            Document={
                "S3Object": {
                    "Bucket": bucket,
                    "Name": s3_key,
                }
            },
        )

        # Extract just text from blocks
        blocks = response.get("Blocks", [])
        lines = [block["Text"] for block in blocks if block.get("BlockType") == "LINE"]

        return "\n".join(lines)

    except ClientError as e:
        raise TextractError(f"Failed to extract text from s3://{bucket}/{s3_key}: {e}") from e
    except Exception as e:
        raise TextractError(
            f"Unexpected error extracting text from s3://{bucket}/{s3_key}: {e}"
        ) from e
