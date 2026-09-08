"""Tests for S3 module."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from aws_simple import s3
from aws_simple.exceptions import S3Error

pytestmark = pytest.mark.unit

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
    """Test successful object listing (single page, not truncated)."""
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "docs/file1.txt"},
            {"Key": "docs/file2.txt"},
            {"Key": "docs/file3.txt"},
        ],
        "IsTruncated": False,
    }

    objects = s3.list_objects(prefix="docs/")

    assert objects == ["docs/file1.txt", "docs/file2.txt", "docs/file3.txt"]
    mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="docs/")


def test_list_objects_empty(mock_s3_client: MagicMock) -> None:
    """Test listing with no objects."""
    mock_s3_client.list_objects_v2.return_value = {}

    objects = s3.list_objects(prefix="empty/")

    assert objects == []
    mock_s3_client.list_objects_v2.assert_called_once_with(Bucket="test-bucket", Prefix="empty/")


def test_list_objects_paginates_all_pages(mock_s3_client: MagicMock) -> None:
    """Test that listing follows IsTruncated/NextContinuationToken across pages."""
    mock_s3_client.list_objects_v2.side_effect = [
        {
            "Contents": [{"Key": "docs/file1.txt"}, {"Key": "docs/file2.txt"}],
            "IsTruncated": True,
            "NextContinuationToken": "token-1",
        },
        {
            "Contents": [{"Key": "docs/file3.txt"}],
            "IsTruncated": True,
            "NextContinuationToken": "token-2",
        },
        {
            "Contents": [{"Key": "docs/file4.txt"}],
            "IsTruncated": False,
        },
    ]

    objects = s3.list_objects(prefix="docs/")

    assert objects == [
        "docs/file1.txt",
        "docs/file2.txt",
        "docs/file3.txt",
        "docs/file4.txt",
    ]
    assert mock_s3_client.list_objects_v2.call_count == 3
    mock_s3_client.list_objects_v2.assert_any_call(Bucket="test-bucket", Prefix="docs/")
    mock_s3_client.list_objects_v2.assert_any_call(
        Bucket="test-bucket", Prefix="docs/", ContinuationToken="token-1"
    )
    mock_s3_client.list_objects_v2.assert_any_call(
        Bucket="test-bucket", Prefix="docs/", ContinuationToken="token-2"
    )


def test_list_objects_with_max_keys_single_page(mock_s3_client: MagicMock) -> None:
    """Test listing with a max_keys cap smaller than the page size."""
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "file.txt"}]}

    s3.list_objects(prefix="docs/", max_keys=100)

    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="docs/", MaxKeys=100
    )


def test_list_objects_with_max_keys_stops_early_across_pages(mock_s3_client: MagicMock) -> None:
    """Test that max_keys caps the total across multiple pages and trims the result."""
    mock_s3_client.list_objects_v2.return_value = {
        "Contents": [{"Key": "file1.txt"}, {"Key": "file2.txt"}, {"Key": "file3.txt"}],
        "IsTruncated": True,
        "NextContinuationToken": "token-1",
    }

    objects = s3.list_objects(prefix="docs/", max_keys=2)

    assert objects == ["file1.txt", "file2.txt"]
    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="docs/", MaxKeys=2
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


def test_upload_file_accepts_path_object(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """A pathlib.Path local path is converted to a string for boto3."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    s3.upload_file(test_file, "uploads/test.txt", bucket="custom-bucket")

    mock_s3_client.upload_file.assert_called_once_with(
        str(test_file), "custom-bucket", "uploads/test.txt"
    )


def test_upload_file_error_message_names_destination(
    mock_s3_client: MagicMock, tmp_path: Path
) -> None:
    """The upload error message includes the full s3:// destination."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "upload_file")
    mock_s3_client.upload_file.side_effect = error

    with pytest.raises(S3Error) as exc_info:
        s3.upload_file(test_file, "uploads/test.txt", bucket="my-bucket")

    assert "s3://my-bucket/uploads/test.txt" in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_upload_file_not_found_never_calls_s3(mock_s3_client: MagicMock) -> None:
    """A missing local file is rejected before any S3 call is made."""
    with pytest.raises(S3Error, match="Local file not found"):
        s3.upload_file("/nonexistent/file.txt", "uploads/test.txt")

    mock_s3_client.upload_file.assert_not_called()


def test_download_file_custom_bucket(mock_s3_client: MagicMock, tmp_path: Path) -> None:
    """A custom bucket overrides the configured default on download."""
    target_file = tmp_path / "downloaded.txt"

    s3.download_file("docs/test.txt", target_file, bucket="custom-bucket")

    mock_s3_client.download_file.assert_called_once_with(
        "custom-bucket", "docs/test.txt", str(target_file)
    )


def test_download_file_error_message_names_source(
    mock_s3_client: MagicMock, tmp_path: Path
) -> None:
    """The download error message includes both source and destination."""
    target_file = tmp_path / "file.txt"
    error = ClientError({"Error": {"Code": "NoSuchKey", "Message": "gone"}}, "download_file")
    mock_s3_client.download_file.side_effect = error

    with pytest.raises(S3Error) as exc_info:
        s3.download_file("docs/missing.txt", target_file, bucket="my-bucket")

    assert "s3://my-bucket/docs/missing.txt" in str(exc_info.value)
    assert str(target_file) in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_read_object_returns_body_bytes(mock_s3_client: MagicMock) -> None:
    """read_object returns exactly what Body.read() produced."""
    mock_body = MagicMock()
    mock_body.read.return_value = b"\x00binary\xff"
    mock_s3_client.get_object.return_value = {"Body": mock_body}

    assert s3.read_object("docs/blob.bin") == b"\x00binary\xff"
    mock_body.read.assert_called_once_with()


def test_read_object_error_message_names_object(mock_s3_client: MagicMock) -> None:
    """The read error message includes the s3:// location and the cause."""
    error = ClientError({"Error": {"Code": "NoSuchKey", "Message": "gone"}}, "get_object")
    mock_s3_client.get_object.side_effect = error

    with pytest.raises(S3Error) as exc_info:
        s3.read_object("docs/x.txt", bucket="my-bucket")

    assert "s3://my-bucket/docs/x.txt" in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_list_objects_defaults_to_empty_prefix(mock_s3_client: MagicMock) -> None:
    """Calling list_objects with no arguments lists the whole bucket."""
    mock_s3_client.list_objects_v2.return_value = {"Contents": [{"Key": "a.txt"}]}

    assert s3.list_objects() == ["a.txt"]
    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket", Prefix="", MaxKeys=1000
    )


def test_list_objects_custom_bucket(mock_s3_client: MagicMock) -> None:
    """A custom bucket overrides the configured default on listing."""
    mock_s3_client.list_objects_v2.return_value = {"Contents": []}

    assert s3.list_objects(prefix="docs/", bucket="custom-bucket") == []
    assert mock_s3_client.list_objects_v2.call_args.kwargs["Bucket"] == "custom-bucket"


def test_list_objects_error_message_names_prefix(mock_s3_client: MagicMock) -> None:
    """The listing error message includes the bucket and prefix."""
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "list_objects_v2")
    mock_s3_client.list_objects_v2.side_effect = error

    with pytest.raises(S3Error) as exc_info:
        s3.list_objects(prefix="docs/", bucket="my-bucket")

    assert "s3://my-bucket/docs/" in str(exc_info.value)
    assert exc_info.value.__cause__ is error


def test_object_exists_custom_bucket(mock_s3_client: MagicMock) -> None:
    """A custom bucket overrides the configured default on the existence check."""
    mock_s3_client.head_object.return_value = {"ContentLength": MOCK_CONTENT_LENGTH}

    assert s3.object_exists("docs/x.txt", bucket="custom-bucket") is True
    mock_s3_client.head_object.assert_called_once_with(Bucket="custom-bucket", Key="docs/x.txt")


def test_object_exists_non_404_not_found_code_raises(mock_s3_client: MagicMock) -> None:
    """Only the literal "404" code maps to False; NoSuchKey still raises."""
    mock_s3_client.head_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "head_object"
    )

    with pytest.raises(S3Error, match="Failed to check"):
        s3.object_exists("docs/missing.txt")
