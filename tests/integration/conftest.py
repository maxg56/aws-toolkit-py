"""
Fixtures for the integration suite, which runs against a real S3 endpoint.

Unlike the mocked unit suite these tests speak HTTP to an actual
S3 implementation (LocalStack by default), so they prove that the requests
the library builds are genuinely accepted -- a wrong parameter name, a bad
continuation token or a malformed body fails here where a mock would happily
accept it.

LocalStack is driven exclusively through the library's public configuration
(``AWS_ENDPOINT_URL`` and the credential variables); nothing here patches
library internals.

Start LocalStack and run the suite::

    docker run --rm -d -p 4566:4566 -e SERVICES=s3 localstack/localstack:3
    pytest -m integration

Environment variables honoured here:

``AWS_ENDPOINT_URL`` / ``AWS_S3_ENDPOINT_URL``
    Endpoint to test against (default ``http://127.0.0.1:4566``). Any
    S3-compatible endpoint works.
``AWS_SIMPLE_INTEGRATION_TIMEOUT``
    Seconds to wait for the endpoint to become ready (default 60).
``AWS_SIMPLE_INTEGRATION_REQUIRED``
    When set to a truthy value an unreachable endpoint is a failure instead
    of a skip. CI sets it so a job whose container never came up cannot pass
    by silently skipping every test.
"""

import os
import time
from collections.abc import Callable, Generator, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, NamedTuple
from urllib.parse import urlsplit
from uuid import uuid4

import boto3
import pytest

from aws_simple._clients import AWSClients

DEFAULT_ENDPOINT_URL = "http://127.0.0.1:4566"
REGION = "us-east-1"

# LocalStack accepts any credentials; these exist only so botocore signs the
# request instead of failing the default credential chain.
ACCESS_KEY_ID = "test"
SECRET_ACCESS_KEY = "test"

READINESS_POLL_SECONDS = 0.5
DEFAULT_READINESS_TIMEOUT_SECONDS = 60.0

# One more than S3's 1000-key page size, so listing the prefix cannot be
# served without following a ContinuationToken.
PAGINATED_KEY_COUNT = 1001
PAGINATED_PREFIX = "many/"

# Keys outside PAGINATED_PREFIX, so prefix filtering is exercised alongside
# pagination. "other/" sorts after "many/" lexicographically.
DECOY_PREFIX = "other/"
DECOY_KEY_COUNT = 3

UPLOAD_WORKERS = 16


def _truthy(value: str | None) -> bool:
    """Whether an environment variable is set to something meaning "yes"."""
    return (value or "").strip().lower() not in ("", "0", "false", "no", "off")


def _new_bucket_name() -> str:
    """Build a DNS-compliant bucket name unique to this test run."""
    return f"aws-simple-it-{uuid4().hex[:16]}"


def _wait_until_ready(client: Any, timeout: float) -> Exception | None:
    """
    Block until the endpoint answers an S3 call, or the timeout expires.

    A successful ``ListBuckets`` is a stronger readiness signal than an HTTP
    health probe: LocalStack can accept connections before S3 itself is able
    to serve requests. Returns the last error on timeout, else ``None``.
    """
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None

    while True:
        try:
            client.list_buckets()
            return None
        except Exception as exc:  # noqa: BLE001 - any failure means "not ready yet"
            last_error = exc
        if time.monotonic() >= deadline:
            return last_error
        time.sleep(READINESS_POLL_SECONDS)


def _empty_bucket(client: Any, bucket: str) -> None:
    """Delete every object in a bucket, paginating over its contents."""
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        contents = page.get("Contents", [])
        if contents:
            client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
            )


def _delete_bucket(client: Any, bucket: str) -> None:
    """Remove a bucket and everything in it."""
    _empty_bucket(client, bucket)
    client.delete_bucket(Bucket=bucket)


def _put_many(client: Any, bucket: str, keys: Iterable[str]) -> None:
    """Upload a batch of tiny objects concurrently."""
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as pool:
        for _ in pool.map(
            lambda key: client.put_object(Bucket=bucket, Key=key, Body=b"x"),
            keys,
        ):
            pass


@pytest.fixture(scope="session")
def s3_endpoint_url() -> str:
    """Endpoint the suite runs against."""
    return (
        os.environ.get("AWS_S3_ENDPOINT_URL")
        or os.environ.get("AWS_ENDPOINT_URL")
        or DEFAULT_ENDPOINT_URL
    )


@pytest.fixture(scope="session")
def raw_s3(s3_endpoint_url: str) -> Any:
    """
    An independent boto3 S3 client used to arrange and verify test state.

    Built directly here rather than borrowed from ``AWSClients`` so the
    library is never used to verify itself: when a test asserts that
    ``s3.put_object`` wrote an object, the check goes through this client.

    Doubles as the readiness gate for the whole suite.
    """
    client = boto3.client(
        "s3",
        region_name=REGION,
        endpoint_url=s3_endpoint_url,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
    )

    timeout = float(
        os.environ.get("AWS_SIMPLE_INTEGRATION_TIMEOUT", DEFAULT_READINESS_TIMEOUT_SECONDS)
    )
    error = _wait_until_ready(client, timeout)
    if error is not None:
        message = (
            f"No S3 endpoint answered at {s3_endpoint_url} within {timeout:g}s "
            f"({type(error).__name__}: {error}). Start LocalStack with "
            f"'docker run --rm -d -p 4566:4566 -e SERVICES=s3 localstack/localstack:3', "
            f"or point AWS_ENDPOINT_URL at another S3-compatible endpoint."
        )
        if _truthy(os.environ.get("AWS_SIMPLE_INTEGRATION_REQUIRED")):
            pytest.fail(message, pytrace=False)
        pytest.skip(message)

    return client


@pytest.fixture(scope="session")
def default_bucket(raw_s3: Any) -> Generator[str, None, None]:
    """
    The bucket ``AWS_S3_BUCKET`` points at, for the implicit-bucket code path.

    Shared by the whole session, so tests using it must namespace their keys.
    """
    name = _new_bucket_name()
    raw_s3.create_bucket(Bucket=name)
    try:
        yield name
    finally:
        _delete_bucket(raw_s3, name)


@pytest.fixture(autouse=True)
def mock_env_vars(
    monkeypatch: pytest.MonkeyPatch,
    s3_endpoint_url: str,
    default_bucket: str,
) -> None:
    """
    Point the library at the S3 endpoint under test.

    Deliberately shadows the identically named autouse fixture in
    ``tests/conftest.py``, which strips the endpoint and credential variables
    so unit tests can never pick up a developer's real AWS configuration.
    Integration tests need the opposite.

    Only ``AWS_ENDPOINT_URL`` is set: ``AWS_S3_ENDPOINT_URL`` is cleared so
    the S3 client is exercised falling back to the generic endpoint variable.
    """
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("AWS_S3_BUCKET", default_bucket)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", ACCESS_KEY_ID)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", SECRET_ACCESS_KEY)
    monkeypatch.setenv("AWS_ENDPOINT_URL", s3_endpoint_url)
    for name in ("AWS_S3_ENDPOINT_URL", "AWS_PROFILE", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    # An HTTP proxy configured in the developer's shell must not swallow
    # calls to a local endpoint; botocore honours no_proxy for that.
    host = urlsplit(s3_endpoint_url).hostname or "localhost"
    for name in ("no_proxy", "NO_PROXY"):
        current = os.environ.get(name, "")
        monkeypatch.setenv(name, f"{current},{host}" if current else host)


@pytest.fixture(autouse=True)
def _fresh_clients() -> Generator[None, None, None]:
    """Rebuild the cached S3 client so it picks up the endpoint above."""
    AWSClients.reset_clients()
    yield
    AWSClients.reset_clients()


@pytest.fixture
def bucket_factory(raw_s3: Any) -> Generator[Callable[[], str], None, None]:
    """Create buckets on demand, removing them when the test finishes."""
    created: list[str] = []

    def make() -> str:
        name = _new_bucket_name()
        raw_s3.create_bucket(Bucket=name)
        created.append(name)
        return name

    try:
        yield make
    finally:
        for name in created:
            _delete_bucket(raw_s3, name)


@pytest.fixture
def bucket(bucket_factory: Callable[[], str]) -> str:
    """A freshly created, empty bucket for a single test."""
    return bucket_factory()


class ManyKeys(NamedTuple):
    """A bucket pre-filled with more objects than fit in one listing page."""

    bucket: str
    prefix: str
    keys: list[str]
    """Keys under ``prefix``, in the lexicographic order S3 returns them."""
    other_keys: list[str]
    """Keys outside ``prefix``, in lexicographic order."""


def _paginated_keys() -> list[str]:
    """
    Build the keys stored under ``PAGINATED_PREFIX``, in lexicographic order.

    Zero padded so lexicographic and numeric order agree, which lets a test
    assert exactly *which* keys a trimmed or paginated listing returned.
    """
    width = len(str(PAGINATED_KEY_COUNT - 1))
    return [f"{PAGINATED_PREFIX}key-{index:0{width}d}" for index in range(PAGINATED_KEY_COUNT)]


def _decoy_keys() -> list[str]:
    """Build the keys stored outside ``PAGINATED_PREFIX``."""
    return [f"{DECOY_PREFIX}key-{index}" for index in range(DECOY_KEY_COUNT)]


@pytest.fixture(scope="module")
def many_keys(raw_s3: Any) -> Generator[ManyKeys, None, None]:
    """
    A bucket holding more objects than fit in one ``list_objects_v2`` page.

    ``PAGINATED_KEY_COUNT`` keys live under ``PAGINATED_PREFIX`` and a few
    decoys under ``DECOY_PREFIX``, so prefix filtering is exercised together
    with pagination. Module-scoped: filling it is by far the slowest part of
    this suite, and every test that reads it leaves it untouched.
    """
    name = _new_bucket_name()
    keys = _paginated_keys()
    other_keys = _decoy_keys()

    raw_s3.create_bucket(Bucket=name)
    try:
        _put_many(raw_s3, name, keys + other_keys)
        yield ManyKeys(bucket=name, prefix=PAGINATED_PREFIX, keys=keys, other_keys=other_keys)
    finally:
        _delete_bucket(raw_s3, name)
