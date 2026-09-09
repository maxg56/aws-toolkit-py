"""Tests for the programmatic configure() API."""

import os
from unittest.mock import patch

import pytest

from aws_simple import configure
from aws_simple._clients import AWSClients
from aws_simple.config import config

pytestmark = pytest.mark.unit


def test_configure_overrides_take_precedence_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configure() value wins over the matching environment variable."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    configure(region="eu-west-3", bucket="my-bucket")

    assert config.aws_region == "eu-west-3"
    assert config.s3_bucket == "my-bucket"


def test_configure_leaves_unset_fields_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """Omitting a parameter keeps the environment-derived value."""
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")

    configure(bucket="only-the-bucket")

    assert config.aws_region == "ap-southeast-1"
    assert config.s3_bucket == "only-the-bucket"


def test_configure_resets_cached_clients_so_new_settings_apply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Regression test for the documented trap: a client built before configure()
    is called must not keep serving the stale region.
    """
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()  # client built for the original region
        assert mock_session.call_args.kwargs["region_name"] == "us-east-1"

        configure(region="eu-west-3")
        AWSClients.get_s3_client()  # must rebuild against the new region

    assert mock_session.call_args.kwargs["region_name"] == "eu-west-3"
    assert mock_session.call_count == 2


def test_configure_without_bucket_still_falls_back_to_required_env_var(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """configure(region=...) alone does not require every other field to be set."""
    monkeypatch.setenv("AWS_S3_BUCKET", "env-bucket")

    configure(region="eu-west-3")

    assert config.s3_bucket == "env-bucket"


def test_configure_credentials_and_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """configure() covers credentials and per-service endpoints, not just region/bucket."""
    configure(
        endpoint_url="http://localhost:4566",
        s3_endpoint_url="http://localhost:9000",
        textract_region="eu-central-1",
        textract_endpoint_url="http://localhost:9001",
        bedrock_region="eu-north-1",
        bedrock_endpoint_url="http://localhost:9002",
        bedrock_model_id="amazon.titan-text-express-v1",
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        session_token="FQoGZXIvYXdzEXAMPLESESSIONTOKEN",
    )

    assert config.endpoint_url == "http://localhost:4566"
    assert config.s3_endpoint_url == "http://localhost:9000"
    assert config.textract_region == "eu-central-1"
    assert config.textract_endpoint_url == "http://localhost:9001"
    assert config.bedrock_region == "eu-north-1"
    assert config.bedrock_endpoint_url == "http://localhost:9002"
    assert config.bedrock_model_id == "amazon.titan-text-express-v1"
    assert config.has_explicit_credentials is True


def test_configure_retry_and_timeout_settings() -> None:
    """configure() also covers the botocore retry/timeout knobs from #33."""
    configure(max_attempts=7, retry_mode="adaptive", connect_timeout=2, read_timeout=15)

    assert config.max_attempts == 7
    assert config.retry_mode == "adaptive"
    assert config.connect_timeout == 2
    assert config.read_timeout == 15


def test_configure_does_not_mutate_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """configure() is purely in-process and never writes to os.environ."""
    monkeypatch.delenv("AWS_REGION", raising=False)

    configure(region="eu-west-3")

    assert "AWS_REGION" not in os.environ
    assert config.aws_region == "eu-west-3"
