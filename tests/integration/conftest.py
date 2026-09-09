"""
Fixtures for the LocalStack integration suite.

These tests hit a real S3-compatible endpoint (LocalStack) instead of a
mocked boto3 client, so they need something listening at AWS_ENDPOINT_URL
(default: http://localhost:4566). They are excluded from the default
`pytest` run (see the `-m "not integration"` addopts in pyproject.toml) and
must be run explicitly with `pytest -m integration`.

If LocalStack is not reachable, the bucket fixtures below skip every test
that depends on them rather than failing, so an accidental `pytest -m
integration` run on a laptop without LocalStack running fails loudly with a
skip reason instead of a wall of connection errors.
"""

import os
import uuid
from collections.abc import Callable, Generator

import pytest

LOCALSTACK_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")


@pytest.fixture(scope="session", autouse=True)
def _localstack_env() -> None:
    """Point aws-simple at LocalStack unless the environment already does."""
    os.environ.setdefault("AWS_ENDPOINT_URL", LOCALSTACK_ENDPOINT)
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("AWS_S3_BUCKET", "aws-simple-integration-placeholder")


@pytest.fixture(scope="session")
def bucket_factory() -> Generator[Callable[[], str], None, None]:
    """Create throwaway S3 buckets against LocalStack, cleaned up at session end."""
    from aws_simple._clients import AWSClients

    client = AWSClients.get_s3_client()
    created: list[str] = []

    def _create() -> str:
        name = f"aws-simple-it-{uuid.uuid4().hex[:12]}"
        try:
            client.create_bucket(Bucket=name)
        except Exception as exc:
            pytest.skip(f"LocalStack is not reachable at {LOCALSTACK_ENDPOINT}: {exc}")
        created.append(name)
        return name

    yield _create

    for name in created:
        try:
            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=name):
                objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if objects:
                    client.delete_objects(Bucket=name, Delete={"Objects": objects})
            client.delete_bucket(Bucket=name)
        except Exception:
            pass  # best-effort cleanup; a leftover LocalStack bucket is harmless


@pytest.fixture
def bucket(bucket_factory: Callable[[], str]) -> str:
    """A fresh, empty bucket for a single test, also set as the default bucket."""
    from aws_simple.config import configure

    name = bucket_factory()
    configure(bucket=name)
    return name
