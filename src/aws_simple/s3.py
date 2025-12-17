"""S3 operations module."""

from pathlib import Path
from typing import cast

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


def list_objects(
    prefix: str = "",
    bucket: str | None = None,
    max_keys: int = 1000,
) -> list[str]:
    """
    List objects in S3 bucket.

    Args:
        prefix: Filter objects by prefix
        bucket: S3 bucket name (uses AWS_S3_BUCKET env var if not specified)
        max_keys: Maximum number of keys to return

    Returns:
        List of S3 object keys

    Raises:
        S3Error: If listing fails
    """
    bucket = bucket or config.s3_bucket

    try:
        client = AWSClients.get_s3_client()
        response = client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=max_keys,
        )

        if "Contents" not in response:
            return []

        return [obj["Key"] for obj in response["Contents"]]
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
