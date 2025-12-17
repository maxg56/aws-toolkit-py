"""Tests for Textract module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from aws_simple import textract
from aws_simple.exceptions import TextractError
from aws_simple.models.textract import TextractDocument

# Test data constants
EXPECTED_HIGH_CONFIDENCE = 99.5


def test_extract_text_from_file_success(
    mock_textract_client: MagicMock, sample_textract_response: dict, tmp_path: Path
) -> None:
    """Test successful text extraction from local file."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")

    mock_textract_client.analyze_document.return_value = sample_textract_response

    doc = textract.extract_text_from_file(str(test_file))

    assert isinstance(doc, TextractDocument)
    assert len(doc.pages) == 1
    assert doc.full_text != ""
    assert "Invoice #12345" in doc.full_text

    mock_textract_client.analyze_document.assert_called_once()
    call_args = mock_textract_client.analyze_document.call_args
    assert call_args.kwargs["FeatureTypes"] == ["TABLES"]
    assert "Bytes" in call_args.kwargs["Document"]


def test_extract_text_from_file_not_found(mock_textract_client: MagicMock) -> None:
    """Test extraction with non-existent file."""
    with pytest.raises(TextractError, match="Local file not found"):
        textract.extract_text_from_file("/nonexistent/file.pdf")


def test_extract_text_from_file_client_error(
    mock_textract_client: MagicMock, tmp_path: Path
) -> None:
    """Test extraction with Textract client error."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")

    mock_textract_client.analyze_document.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameterException", "Message": "Invalid document"}},
        "analyze_document",
    )

    with pytest.raises(TextractError, match="Failed to extract text"):
        textract.extract_text_from_file(str(test_file))


def test_extract_text_from_s3_success(
    mock_textract_client: MagicMock, sample_textract_response: dict
) -> None:
    """Test successful text extraction from S3."""
    mock_textract_client.analyze_document.return_value = sample_textract_response

    doc = textract.extract_text_from_s3("docs/invoice.pdf")

    assert isinstance(doc, TextractDocument)
    assert len(doc.pages) == 1

    mock_textract_client.analyze_document.assert_called_once()
    call_args = mock_textract_client.analyze_document.call_args
    assert call_args.kwargs["Document"]["S3Object"]["Bucket"] == "test-bucket"
    assert call_args.kwargs["Document"]["S3Object"]["Name"] == "docs/invoice.pdf"
    assert call_args.kwargs["FeatureTypes"] == ["TABLES"]


def test_extract_text_from_s3_custom_bucket(
    mock_textract_client: MagicMock, sample_textract_response: dict
) -> None:
    """Test extraction from S3 with custom bucket."""
    mock_textract_client.analyze_document.return_value = sample_textract_response

    textract.extract_text_from_s3("docs/invoice.pdf", bucket="custom-bucket")

    call_args = mock_textract_client.analyze_document.call_args
    assert call_args.kwargs["Document"]["S3Object"]["Bucket"] == "custom-bucket"


def test_extract_text_from_s3_client_error(mock_textract_client: MagicMock) -> None:
    """Test S3 extraction with client error."""
    mock_textract_client.analyze_document.side_effect = ClientError(
        {"Error": {"Code": "InvalidS3ObjectException", "Message": "Object not found"}},
        "analyze_document",
    )

    with pytest.raises(TextractError, match="Failed to extract text"):
        textract.extract_text_from_s3("docs/missing.pdf")


def test_extract_text_simple_from_file_success(
    mock_textract_client: MagicMock, tmp_path: Path
) -> None:
    """Test simple text extraction from local file."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")

    mock_textract_client.detect_document_text.return_value = {
        "Blocks": [
            {"BlockType": "LINE", "Text": "Line 1"},
            {"BlockType": "LINE", "Text": "Line 2"},
            {"BlockType": "WORD", "Text": "Word"},
        ]
    }

    text = textract.extract_text_simple_from_file(str(test_file))

    assert text == "Line 1\nLine 2"
    mock_textract_client.detect_document_text.assert_called_once()


def test_extract_text_simple_from_s3_success(mock_textract_client: MagicMock) -> None:
    """Test simple text extraction from S3."""
    mock_textract_client.detect_document_text.return_value = {
        "Blocks": [
            {"BlockType": "LINE", "Text": "First line"},
            {"BlockType": "LINE", "Text": "Second line"},
        ]
    }

    text = textract.extract_text_simple_from_s3("docs/simple.pdf")

    assert text == "First line\nSecond line"
    call_args = mock_textract_client.detect_document_text.call_args
    assert call_args.kwargs["Document"]["S3Object"]["Bucket"] == "test-bucket"
    assert call_args.kwargs["Document"]["S3Object"]["Name"] == "docs/simple.pdf"


def test_textract_document_structure(
    mock_textract_client: MagicMock, sample_textract_response: dict, tmp_path: Path
) -> None:
    """Test TextractDocument structure and data access."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")

    mock_textract_client.analyze_document.return_value = sample_textract_response

    doc = textract.extract_text_from_file(str(test_file))

    # Test pages
    assert len(doc.pages) == 1
    page = doc.pages[0]
    assert page.page_number == 1

    # Test lines
    assert len(page.lines) == 2
    assert page.lines[0].text == "Invoice #12345"
    assert page.lines[0].confidence == EXPECTED_HIGH_CONFIDENCE
    assert "top" in page.lines[0].bounding_box

    # Test tables
    assert len(page.tables) == 1
    table = page.tables[0]
    assert table.rows == 2
    assert table.columns == 2
    assert table.cells[0][0] == "Item"
    assert table.cells[0][1] == "Price"
    assert table.cells[1][0] == "Product A"
    assert table.cells[1][1] == "$10"

    # Test full text
    assert "Invoice #12345" in doc.full_text
    assert "Date: 2024-01-15" in doc.full_text

    # Test metadata
    assert "total_pages" in doc.metadata
    assert doc.metadata["total_pages"] == 1


def test_textract_document_to_dict(
    mock_textract_client: MagicMock, sample_textract_response: dict, tmp_path: Path
) -> None:
    """Test TextractDocument serialization to dict."""
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"PDF content")

    mock_textract_client.analyze_document.return_value = sample_textract_response

    doc = textract.extract_text_from_file(str(test_file))
    doc_dict = doc.to_dict()

    assert isinstance(doc_dict, dict)
    assert "pages" in doc_dict
    assert "full_text" in doc_dict
    assert "metadata" in doc_dict
    assert len(doc_dict["pages"]) == 1

    page_dict = doc_dict["pages"][0]
    assert "page_number" in page_dict
    assert "lines" in page_dict
    assert "tables" in page_dict
    assert "raw_text" in page_dict

    # Verify it's JSON-serializable
    import json

    json_str = json.dumps(doc_dict)
    assert isinstance(json_str, str)
