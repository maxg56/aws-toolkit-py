"""
Integration tests for the S3 object operations against a real endpoint.

Covers the read/write pair (``put_object`` / ``read_object``), the file
transfer helpers, the ``object_exists`` 404 branch, and the ``delete_object``
and ``copy_object`` operations. Every assertion about stored state is made
with an independent boto3 client (``raw_s3``) so the library is never used to
verify itself.
"""

from pathlib import Path
from typing import Any

import pytest

from aws_simple import s3
from aws_simple.exceptions import S3Error

pytestmark = pytest.mark.integration

# Exercises the parts of a key that need URL encoding on the wire: a space, a
# plus (which decodes to a space if the encoding is wrong), a literal percent
# escape, and non-ASCII text.
AWKWARD_KEY = "needs encoding/a b+c%20d é.txt"


def _body(raw_s3: Any, bucket: str, key: str) -> bytes:
    """Read an object's bytes without going through the library."""
    return bytes(raw_s3.get_object(Bucket=bucket, Key=key)["Body"].read())


class TestPutAndReadObject:
    """``put_object`` writes bytes that ``read_object`` reads back."""

    def test_round_trips_bytes(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object("data/blob.bin", b"\x00\x01\xfe\xff", bucket=bucket)

        assert _body(raw_s3, bucket, "data/blob.bin") == b"\x00\x01\xfe\xff"
        assert s3.read_object("data/blob.bin", bucket=bucket) == b"\x00\x01\xfe\xff"

    def test_encodes_str_body_as_utf8(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object("data/note.txt", "héllo wörld", bucket=bucket)

        assert _body(raw_s3, bucket, "data/note.txt") == "héllo wörld".encode()
        assert s3.read_object("data/note.txt", bucket=bucket).decode() == "héllo wörld"

    def test_accepts_an_empty_body(self, bucket: str, raw_s3: Any) -> None:
        """A zero-length object is a valid object, not a missing one."""
        s3.put_object("data/empty.txt", b"", bucket=bucket)

        assert _body(raw_s3, bucket, "data/empty.txt") == b""
        assert s3.object_exists("data/empty.txt", bucket=bucket) is True

    def test_overwrites_an_existing_key(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object("data/note.txt", b"first", bucket=bucket)
        s3.put_object("data/note.txt", b"second", bucket=bucket)

        assert _body(raw_s3, bucket, "data/note.txt") == b"second"

    def test_round_trips_a_key_needing_url_encoding(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object(AWKWARD_KEY, b"awkward", bucket=bucket)

        assert _body(raw_s3, bucket, AWKWARD_KEY) == b"awkward"
        assert s3.read_object(AWKWARD_KEY, bucket=bucket) == b"awkward"
        assert s3.list_objects(prefix="needs encoding/", bucket=bucket) == [AWKWARD_KEY]

    def test_uses_default_bucket_from_env(self, default_bucket: str, raw_s3: Any) -> None:
        """With no ``bucket`` argument the ``AWS_S3_BUCKET`` bucket is used."""
        key = "put-default/note.txt"
        s3.put_object(key, b"default")
        try:
            assert _body(raw_s3, default_bucket, key) == b"default"
            assert s3.read_object(key) == b"default"
        finally:
            raw_s3.delete_object(Bucket=default_bucket, Key=key)

    def test_read_object_missing_key_raises_s3_error(self, bucket: str) -> None:
        with pytest.raises(S3Error, match="Failed to read"):
            s3.read_object("data/absent.txt", bucket=bucket)


class TestObjectExists:
    """``object_exists`` maps a ``HeadObject`` 404 to ``False``."""

    def test_true_for_an_existing_key(self, bucket: str) -> None:
        s3.put_object("data/present.txt", b"here", bucket=bucket)

        assert s3.object_exists("data/present.txt", bucket=bucket) is True

    def test_false_for_a_missing_key(self, bucket: str) -> None:
        """
        The 404 branch, against a real endpoint.

        ``HeadObject`` has no response body, so botocore reports the bare
        HTTP status as the error code rather than ``NoSuchKey``. That the
        code really is ``"404"`` is exactly what a mock cannot prove.
        """
        assert s3.object_exists("data/absent.txt", bucket=bucket) is False

    def test_false_for_a_key_that_is_only_a_prefix(self, bucket: str) -> None:
        """A prefix shared with real objects is not itself an object."""
        s3.put_object("data/present.txt", b"here", bucket=bucket)

        assert s3.object_exists("data", bucket=bucket) is False
        assert s3.object_exists("data/", bucket=bucket) is False

    def test_false_after_the_key_is_deleted(self, bucket: str) -> None:
        s3.put_object("data/transient.txt", b"bye", bucket=bucket)
        s3.delete_object("data/transient.txt", bucket=bucket)

        assert s3.object_exists("data/transient.txt", bucket=bucket) is False


class TestUploadAndDownloadFile:
    """The managed-transfer helpers move real bytes over the wire."""

    def test_round_trips_a_file(self, bucket: str, tmp_path: Path, raw_s3: Any) -> None:
        source = tmp_path / "source.bin"
        source.write_bytes(b"payload\x00bytes")

        s3.upload_file(source, "files/source.bin", bucket=bucket)
        assert _body(raw_s3, bucket, "files/source.bin") == b"payload\x00bytes"

        destination = tmp_path / "downloaded.bin"
        s3.download_file("files/source.bin", destination, bucket=bucket)
        assert destination.read_bytes() == b"payload\x00bytes"

    def test_download_creates_missing_parent_directories(self, bucket: str, tmp_path: Path) -> None:
        s3.put_object("files/note.txt", b"nested", bucket=bucket)
        destination = tmp_path / "deeply" / "nested" / "note.txt"

        s3.download_file("files/note.txt", destination, bucket=bucket)

        assert destination.read_bytes() == b"nested"

    def test_download_missing_key_raises_s3_error(self, bucket: str, tmp_path: Path) -> None:
        with pytest.raises(S3Error, match="Failed to download"):
            s3.download_file("files/absent.txt", tmp_path / "absent.txt", bucket=bucket)

    def test_upload_missing_local_file_raises_s3_error(self, bucket: str, tmp_path: Path) -> None:
        with pytest.raises(S3Error, match="Local file not found"):
            s3.upload_file(tmp_path / "absent.bin", "files/absent.bin", bucket=bucket)


class TestDeleteObject:
    """``delete_object`` removes a key, and tolerates one that never existed."""

    def test_removes_the_object(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object("data/doomed.txt", b"bye", bucket=bucket)

        s3.delete_object("data/doomed.txt", bucket=bucket)

        assert s3.list_objects(bucket=bucket) == []
        with pytest.raises(raw_s3.exceptions.NoSuchKey):
            raw_s3.get_object(Bucket=bucket, Key="data/doomed.txt")

    def test_is_idempotent_for_a_missing_key(self, bucket: str) -> None:
        """
        ``DeleteObject`` succeeds whether or not the key was there.

        The docstring promises idempotence; only a real endpoint confirms S3
        agrees rather than returning an error the library would wrap.
        """
        s3.delete_object("data/never-existed.txt", bucket=bucket)
        s3.delete_object("data/never-existed.txt", bucket=bucket)

    def test_removes_a_key_needing_url_encoding(self, bucket: str) -> None:
        s3.put_object(AWKWARD_KEY, b"awkward", bucket=bucket)

        s3.delete_object(AWKWARD_KEY, bucket=bucket)

        assert s3.object_exists(AWKWARD_KEY, bucket=bucket) is False

    def test_uses_default_bucket_from_env(self, default_bucket: str, raw_s3: Any) -> None:
        key = "delete-default/note.txt"
        raw_s3.put_object(Bucket=default_bucket, Key=key, Body=b"x")

        s3.delete_object(key)

        assert s3.object_exists(key) is False


class TestCopyObject:
    """``copy_object`` duplicates a key, within a bucket or across buckets."""

    def test_copies_within_a_bucket_leaving_the_source(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object("docs/report.txt", b"contents", bucket=bucket)

        s3.copy_object(
            "docs/report.txt", "archive/report.txt", source_bucket=bucket, dest_bucket=bucket
        )

        assert _body(raw_s3, bucket, "archive/report.txt") == b"contents"
        assert _body(raw_s3, bucket, "docs/report.txt") == b"contents"

    def test_copies_across_buckets(self, bucket_factory: Any, raw_s3: Any) -> None:
        source_bucket = bucket_factory()
        dest_bucket = bucket_factory()
        s3.put_object("docs/report.txt", b"crossing", bucket=source_bucket)

        s3.copy_object(
            "docs/report.txt",
            "incoming/report.txt",
            source_bucket=source_bucket,
            dest_bucket=dest_bucket,
        )

        assert _body(raw_s3, dest_bucket, "incoming/report.txt") == b"crossing"
        assert s3.object_exists("docs/report.txt", bucket=source_bucket) is True

    def test_copies_a_key_needing_url_encoding(self, bucket: str, raw_s3: Any) -> None:
        """
        ``CopySource`` is the classic place a real API rejects what a mock took.

        The source key travels in a header that must be URL encoded; passing
        it as a dict lets botocore do that, and only a real endpoint proves
        the bytes arrived unmangled.
        """
        s3.put_object(AWKWARD_KEY, b"awkward", bucket=bucket)

        s3.copy_object(AWKWARD_KEY, "copied/awkward.txt", source_bucket=bucket, dest_bucket=bucket)

        assert _body(raw_s3, bucket, "copied/awkward.txt") == b"awkward"

    def test_overwrites_an_existing_destination(self, bucket: str, raw_s3: Any) -> None:
        s3.put_object("docs/source.txt", b"new", bucket=bucket)
        s3.put_object("docs/dest.txt", b"old", bucket=bucket)

        s3.copy_object("docs/source.txt", "docs/dest.txt", source_bucket=bucket, dest_bucket=bucket)

        assert _body(raw_s3, bucket, "docs/dest.txt") == b"new"

    def test_missing_source_raises_s3_error(self, bucket: str) -> None:
        with pytest.raises(S3Error, match="Failed to copy"):
            s3.copy_object(
                "docs/absent.txt", "archive/absent.txt", source_bucket=bucket, dest_bucket=bucket
            )

    def test_uses_default_bucket_for_both_ends(self, default_bucket: str, raw_s3: Any) -> None:
        """Omitting both buckets copies inside the ``AWS_S3_BUCKET`` bucket."""
        source_key = "copy-default/source.txt"
        dest_key = "copy-default/dest.txt"
        s3.put_object(source_key, b"same bucket")
        try:
            s3.copy_object(source_key, dest_key)

            assert _body(raw_s3, default_bucket, dest_key) == b"same bucket"
        finally:
            for key in (source_key, dest_key):
                raw_s3.delete_object(Bucket=default_bucket, Key=key)
