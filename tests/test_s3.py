"""Tests for S3 module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from aws_simple import s3
from aws_simple.exceptions import S3Error

# Test data constants
MOCK_CONTENT_LENGTH = 1234


def test_upload_file_success(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """Test successful file upload."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    s3.upload_file(str(test_file), "uploads/test.txt")

    mock_s3_client.upload_file.assert_called_once_with(
        str(test_file), "test-bucket", "uploads/test.txt"
    )


def test_upload_file_not_found(mock_s3_client: MagicMock) -> None:
    """Test upload with non-existent file."""
    with pytest.raises(S3Error, match="Local file not found"):
        s3.upload_file("/nonexistent/file.txt", "uploads/test.txt")


def test_upload_file_client_error(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """Test upload with S3 client error."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    mock_s3_client.upload_file.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}}, "upload_file"
    )

    with pytest.raises(S3Error, match="Failed to upload"):
        s3.upload_file(str(test_file), "uploads/test.txt")


def test_download_file_success(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """Test successful file download."""
    target_file = tmp_path / "downloaded.txt"

    s3.download_file("docs/test.txt", str(target_file))

    mock_s3_client.download_file.assert_called_once_with(
        "test-bucket", "docs/test.txt", str(target_file)
    )


def test_download_file_creates_parent_dirs(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """Test that download creates parent directories."""
    target_file = tmp_path / "nested" / "dirs" / "file.txt"

    s3.download_file("docs/test.txt", str(target_file))

    assert target_file.parent.exists()
    mock_s3_client.download_file.assert_called_once()


def test_download_file_client_error(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """Test download with S3 client error."""
    target_file = tmp_path / "file.txt"

    mock_s3_client.download_file.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}}, "download_file"
    )

    with pytest.raises(S3Error, match="Failed to download"):
        s3.download_file("docs/missing.txt", str(target_file))


def test_read_object_success(mock_s3_client: MagicMock) -> None:
    """Test successful object read."""
    mock_body = MagicMock()
    mock_body.read.return_value = b"file content"
    mock_s3_client.get_object.return_value = {"Body": mock_body}

    content = s3.read_object("docs/test.txt")

    assert content == b"file content"
    mock_s3_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="docs/test.txt")


def test_read_object_custom_bucket(mock_s3_client: MagicMock) -> None:
    """Test read object with custom bucket."""
    mock_body = MagicMock()
    mock_body.read.return_value = b"content"
    mock_s3_client.get_object.return_value = {"Body": mock_body}

    s3.read_object("docs/test.txt", bucket="custom-bucket")

    mock_s3_client.get_object.assert_called_once_with(Bucket="custom-bucket", Key="docs/test.txt")


def test_read_object_client_error(mock_s3_client: MagicMock) -> None:
    """Test read object with client error."""
    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "get_object"
    )

    with pytest.raises(S3Error, match="Failed to read"):
        s3.read_object("docs/test.txt")


def test_list_objects_success(mock_s3_client: MagicMock) -> None:
    """Test successful object listing."""
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "docs/file1.txt"},
            {"Key": "docs/file2.txt"},
            {"Key": "docs/file3.txt"},
        ]
    }

    objects = s3.list_objects(prefix="docs/")

    assert objects == ["docs/file1.txt", "docs/file2.txt", "docs/file3.txt"]
    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="docs/", MaxKeys=1000
    )


def test_list_objects_empty(mock_s3_client: MagicMock) -> None:
    """Test listing with no objects."""
    mock_s3_client.list_objects_v2.return_value = {}

    objects = s3.list_objects(prefix="empty/")

    assert objects == []


def test_list_objects_with_max_keys(mock_s3_client: MagicMock) -> None:
    """Test listing with custom max_keys."""
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "file.txt"}]}

    s3.list_objects(prefix="docs/", max_keys=100)

    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="docs/", MaxKeys=100
    )


def test_list_objects_client_error(mock_s3_client: MagicMock) -> None:
    """Test list objects with client error."""
    mock_s3_client.list_objects_v2.side_effect = ClientError(
        {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}}, "list_objects_v2"
    )

    with pytest.raises(S3Error, match="Failed to list objects"):
        s3.list_objects()


def test_object_exists_true(mock_s3_client: MagicMock) -> None:
    """Test object exists returns True."""
    mock_s3_client.head_object.return_value = {"ContentLength": MOCK_CONTENT_LENGTH}

    assert s3.object_exists("docs/existing.txt") is True
    mock_s3_client.head_object.assert_called_once_with(
        Bucket="test-bucket", Key="docs/existing.txt"
    )


def test_object_exists_false(mock_s3_client: MagicMock) -> None:
    """Test object exists returns False for 404."""
    mock_s3_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "head_object"
    )

    assert s3.object_exists("docs/missing.txt") is False


def test_object_exists_other_error(mock_s3_client: MagicMock) -> None:
    """Test object exists with non-404 error."""
    mock_s3_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "head_object"
    )

    with pytest.raises(S3Error, match="Failed to check"):
        s3.object_exists("docs/test.txt")
