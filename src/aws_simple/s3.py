"""S3 operations module."""

from pathlib import Path
from typing import Any, cast

from botocore.exceptions import ClientError

from ._clients import AWSClients
from .config import config
from .exceptions import S3Error


def upload_file(
    local_path: str | Path,
    s3_key: str,
    bucket: str | None = None,
) -> None:
    """
    Upload a file to S3.

    Args:
        local_path: Path to local file
        s3_key: S3 object key (path in bucket)
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Raises:
        S3Error: If upload fails
    """
    bucket = bucket or config.s3_bucket
    local_path = Path(local_path)

    if not local_path.exists():
        raise S3Error(f"Local file not found: {local_path}")

    try:
        client = AWSClients.get_s3_client()
        client.upload_file(str(local_path), bucket, s3_key)
    except ClientError as e:
        raise S3Error(f"Failed to upload {local_path} to s3://{bucket}/{s3_key}: {e}") from e


def download_file(
    s3_key: str,
    local_path: str | Path,
    bucket: str | None = None,
) -> None:
    """
    Download a file from S3.

    Args:
        s3_key: S3 object key
        local_path: Where to save the file locally
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Raises:
        S3Error: If download fails
    """
    bucket = bucket or config.s3_bucket
    local_path = Path(local_path)

    # Create parent directories if needed
    local_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        client = AWSClients.get_s3_client()
        client.download_file(bucket, s3_key, str(local_path))
    except ClientError as e:
        raise S3Error(f"Failed to download s3://{bucket}/{s3_key} to {local_path}: {e}") from e


def read_object(s3_key: str, bucket: str | None = None) -> bytes:
    """
    Read S3 object content as bytes.

    Args:
        s3_key: S3 object key
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Returns:
        File content as bytes

    Raises:
        S3Error: If read fails
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_s3_client()
        response = client.get_object(Bucket=bucket, Key=s3_key)
        return cast(bytes, response["Body"].read())
    except ClientError as e:
        raise S3Error(f"Failed to read s3://{bucket}/{s3_key}: {e}") from e


def put_object(s3_key: str, body: bytes | str, bucket: str | None = None) -> None:
    """
    Write content directly to an S3 object.

    Mirrors :func:`read_object`: it writes the bytes that ``read_object``
    would return, without needing the content on disk first.

    Args:
        s3_key: S3 object key (path in bucket)
        body: Content to write. ``str`` values are encoded as UTF-8.
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Raises:
        S3Error: If write fails
    """
    bucket = bucket or config.s3_bucket
    data = body.encode("utf-8") if isinstance(body, str) else body

    try:
        client = AWSClients.get_s3_client()
        client.put_object(Bucket=bucket, Key=s3_key, Body=data)
    except ClientError as e:
        raise S3Error(f"Failed to write s3://{bucket}/{s3_key}: {e}") from e


def list_objects(
    prefix: str = "",
    bucket: str | None = None,
    max_keys: int | None = None,
) -> list[str]:
    """
    List objects in S3 bucket.

    Transparently paginates through the ``list_objects_v2`` API (following
    ``IsTruncated``/``NextContinuationToken``) so prefixes with more than
    1000 objects (S3's per-request page size) are returned in full instead
    of being silently truncated to the first page.

    Args:
        prefix: Filter objects by prefix
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)
        max_keys: Optional cap on the *total* number of keys returned across
            all pages. Defaults to ``None``, meaning unlimited: every object
            under the prefix is fetched, no matter how many pages that
            takes. When set, only as many pages as needed to reach this
            many keys are requested, and the result is trimmed to exactly
            `max_keys` entries.

    Returns:
        List of S3 object keys (all matching keys, or at most `max_keys` of
        them if that argument is given)

    Raises:
        S3Error: If listing fails
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_s3_client()
        keys: list[str] = []
        continuation_token: str | None = None

        while True:
            list_kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if continuation_token is not None:
                list_kwargs["ContinuationToken"] = continuation_token
            if max_keys is not None:
                remaining = max_keys - len(keys)
                if remaining <= 0:
                    break
                list_kwargs["MaxKeys"] = min(remaining, 1000)

            response = client.list_objects_v2(**list_kwargs)
            keys.extend(obj["Key"] for obj in response.get("Contents", []))

            if max_keys is not None and len(keys) >= max_keys:
                keys = keys[:max_keys]
                break

            if not response.get("IsTruncated"):
                break

            continuation_token = response.get("NextContinuationToken")
            if continuation_token is None:
                break

        return keys
    except ClientError as e:
        raise S3Error(f"Failed to list objects in s3://{bucket}/{prefix}: {e}") from e


def object_exists(s3_key: str, bucket: str | None = None) -> bool:
    """
    Check if an S3 object exists.

    Args:
        s3_key: S3 object key
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Returns:
        True if object exists, False otherwise

    Raises:
        S3Error: If check fails (other than NotFound)
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_s3_client()
        client.head_object(Bucket=bucket, Key=s3_key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise S3Error(f"Failed to check if s3://{bucket}/{s3_key} exists: {e}") from e


def delete_object(s3_key: str, bucket: str | None = None) -> None:
    """
    Delete an S3 object.

    Deleting a key that does not exist is not an error: S3's ``DeleteObject``
    is idempotent and reports success either way.

    Args:
        s3_key: S3 object key
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)

    Raises:
        S3Error: If delete fails
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_s3_client()
        client.delete_object(Bucket=bucket, Key=s3_key)
    except ClientError as e:
        raise S3Error(f"Failed to delete s3://{bucket}/{s3_key}: {e}") from e


def copy_object(
    source_key: str,
    dest_key: str,
    source_bucket: str | None = None,
    dest_bucket: str | None = None,
) -> None:
    """
    Copy an S3 object, within a bucket or across buckets.

    Args:
        source_key: S3 object key to copy from
        dest_key: S3 object key to copy to
        source_bucket: Source bucket name (uses AWS_S3_BUCKET env var if not
            specified)
        dest_bucket: Destination bucket name (uses AWS_S3_BUCKET env var if
            not specified)

    Raises:
        S3Error: If copy fails
    """
    source_bucket = source_bucket or config.s3_bucket
    dest_bucket = dest_bucket or config.s3_bucket

    try:
        client = AWSClients.get_s3_client()
        client.copy_object(
            Bucket=dest_bucket,
            Key=dest_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
        )
    except ClientError as e:
        raise S3Error(
            f"Failed to copy s3://{source_bucket}/{source_key} "
            f"to s3://{dest_bucket}/{dest_key}: {e}"
        ) from e
