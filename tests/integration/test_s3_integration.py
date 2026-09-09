"""
LocalStack integration tests for the S3 read/write operations.

Unit tests assert what we call on a mocked boto3 client; these prove the
request shape is actually accepted by an S3-compatible service. Run with
`pytest -m integration` (see tests/integration/conftest.py).
"""

import pytest

from aws_simple import s3

pytestmark = pytest.mark.integration


def test_put_object_and_read_object_roundtrip(bucket: str) -> None:
    s3.put_object("greeting.txt", "hello from the integration suite", bucket=bucket)

    assert s3.read_object("greeting.txt", bucket=bucket) == b"hello from the integration suite"


def test_put_object_accepts_bytes(bucket: str) -> None:
    s3.put_object("binary.bin", b"\x00\x01\x02\x03", bucket=bucket)

    assert s3.read_object("binary.bin", bucket=bucket) == b"\x00\x01\x02\x03"


def test_object_exists_is_true_for_a_present_key(bucket: str) -> None:
    s3.put_object("present.txt", "here", bucket=bucket)

    assert s3.object_exists("present.txt", bucket=bucket) is True


def test_object_exists_is_false_for_a_missing_key(bucket: str) -> None:
    """The 404 branch of object_exists: no mock stands in for S3 here."""
    assert s3.object_exists("does-not-exist.txt", bucket=bucket) is False


def test_delete_object_removes_the_key(bucket: str) -> None:
    s3.put_object("to-delete.txt", "bye", bucket=bucket)

    s3.delete_object("to-delete.txt", bucket=bucket)

    assert s3.object_exists("to-delete.txt", bucket=bucket) is False


def test_delete_object_on_a_missing_key_is_not_an_error(bucket: str) -> None:
    s3.delete_object("never-existed.txt", bucket=bucket)


def test_copy_object_within_the_same_bucket(bucket: str) -> None:
    s3.put_object("source.txt", "copy me", bucket=bucket)

    s3.copy_object("source.txt", "dest.txt", source_bucket=bucket, dest_bucket=bucket)

    assert s3.read_object("dest.txt", bucket=bucket) == b"copy me"


def test_list_objects_filters_by_prefix(bucket: str) -> None:
    s3.put_object("docs/a.txt", "a", bucket=bucket)
    s3.put_object("docs/b.txt", "b", bucket=bucket)
    s3.put_object("other/c.txt", "c", bucket=bucket)

    keys = s3.list_objects(prefix="docs/", bucket=bucket)

    assert sorted(keys) == ["docs/a.txt", "docs/b.txt"]
