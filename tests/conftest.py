"""Pytest configuration and fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

# Test data constants for Textract responses
HIGH_CONFIDENCE_INVOICE = 99.5
MEDIUM_CONFIDENCE_DATE = 98.7
BOUNDING_BOX_HEIGHT_SMALL = 0.04
BOUNDING_BOX_HEIGHT_MEDIUM = 0.05
BOUNDING_BOX_WIDTH_MEDIUM = 0.15


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock environment variables for testing."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")


@pytest.fixture
def reset_clients() -> Generator[None, None, None]:
    """Reset AWS clients singleton before and after each test."""
    from aws_simple._clients import AWSClients

    AWSClients.reset_clients()
    yield
    AWSClients.reset_clients()


@pytest.fixture
def mock_s3_client(reset_clients: None) -> MagicMock:
    """Mock S3 client."""
    from unittest.mock import patch

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_textract_client(reset_clients: None) -> MagicMock:
    """Mock Textract client."""
    from unittest.mock import patch

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_bedrock_client(reset_clients: None) -> MagicMock:
    """Mock Bedrock Runtime client."""
    from unittest.mock import patch

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def sample_textract_response() -> dict:
    """Sample Textract API response with blocks."""
    return {
        "DocumentMetadata": {"Pages": 1},
        "Blocks": [
            {
                "BlockType": "PAGE",
                "Id": "page-1",
                "Page": 1,
                "Geometry": {
                    "BoundingBox": {
                        "Width": 1.0,
                        "Height": 1.0,
                        "Left": 0.0,
                        "Top": 0.0,
                    }
                },
            },
            {
                "BlockType": "LINE",
                "Id": "line-1",
                "Page": 1,
                "Text": "Invoice #12345",
                "Confidence": HIGH_CONFIDENCE_INVOICE,
                "Geometry": {
                    "BoundingBox": {
                        "Width": 0.2,
                        "Height": BOUNDING_BOX_HEIGHT_MEDIUM,
                        "Left": 0.1,
                        "Top": 0.1,
                    }
                },
            },
            {
                "BlockType": "LINE",
                "Id": "line-2",
                "Page": 1,
                "Text": "Date: 2024-01-15",
                "Confidence": MEDIUM_CONFIDENCE_DATE,
                "Geometry": {
                    "BoundingBox": {
                        "Width": BOUNDING_BOX_WIDTH_MEDIUM,
                        "Height": BOUNDING_BOX_HEIGHT_SMALL,
                        "Left": 0.1,
                        "Top": 0.2,
                    }
                },
            },
            {
                "BlockType": "TABLE",
                "Id": "table-1",
                "Page": 1,
                "Confidence": 97.5,
                "Relationships": [
                    {"Type": "CHILD", "Ids": ["cell-1", "cell-2", "cell-3", "cell-4"]}
                ],
            },
            {
                "BlockType": "CELL",
                "Id": "cell-1",
                "RowIndex": 1,
                "ColumnIndex": 1,
                "Confidence": 99.0,
                "Relationships": [{"Type": "CHILD", "Ids": ["word-1"]}],
            },
            {
                "BlockType": "CELL",
                "Id": "cell-2",
                "RowIndex": 1,
                "ColumnIndex": 2,
                "Confidence": 99.0,
                "Relationships": [{"Type": "CHILD", "Ids": ["word-2"]}],
            },
            {
                "BlockType": "CELL",
                "Id": "cell-3",
                "RowIndex": 2,
                "ColumnIndex": 1,
                "Confidence": 99.0,
                "Relationships": [{"Type": "CHILD", "Ids": ["word-3"]}],
            },
            {
                "BlockType": "CELL",
                "Id": "cell-4",
                "RowIndex": 2,
                "ColumnIndex": 2,
                "Confidence": 99.0,
                "Relationships": [{"Type": "CHILD", "Ids": ["word-4"]}],
            },
            {"BlockType": "WORD", "Id": "word-1", "Text": "Item"},
            {"BlockType": "WORD", "Id": "word-2", "Text": "Price"},
            {"BlockType": "WORD", "Id": "word-3", "Text": "Product A"},
            {"BlockType": "WORD", "Id": "word-4", "Text": "$10"},
        ],
    }
