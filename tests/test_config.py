"""Tests for config module."""

import pytest

from aws_simple.config import Config
from aws_simple.exceptions import ConfigurationError

pytestmark = pytest.mark.unit


def test_config_required_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that required environment variables are enforced."""
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)

    config = Config()
    with pytest.raises(
        ConfigurationError, match="Missing required environment variable: AWS_S3_BUCKET"
    ):
        _ = config.s3_bucket


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default configuration values."""
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_BEDROCK_MODEL_ID", raising=False)

    config = Config()

    assert config.aws_region == "us-east-1"
    assert config.s3_bucket == "test-bucket"
    assert config.bedrock_model_id == "anthropic.claude-3-5-sonnet-20241022-v2:0"


def test_config_optional_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test optional configuration values."""
    monkeypatch.setenv("AWS_S3_BUCKET", "my-bucket")
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_PROFILE", "my-profile")
    monkeypatch.setenv("AWS_TEXTRACT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_BEDROCK_REGION", "us-east-1")
    monkeypatch.setenv("AWS_BEDROCK_MODEL_ID", "custom-model-id")

    config = Config()

    assert config.aws_region == "eu-west-1"
    assert config.aws_profile == "my-profile"
    assert config.s3_bucket == "my-bucket"
    assert config.textract_region == "us-west-2"
    assert config.bedrock_region == "us-east-1"
    assert config.bedrock_model_id == "custom-model-id"


def test_config_region_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that service-specific regions fall back to AWS_REGION."""
    monkeypatch.setenv("AWS_S3_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    monkeypatch.delenv("AWS_TEXTRACT_REGION", raising=False)
    monkeypatch.delenv("AWS_BEDROCK_REGION", raising=False)

    config = Config()

    assert config.textract_region == "ap-southeast-1"
    assert config.bedrock_region == "ap-southeast-1"


def test_config_endpoint_url_defaults_to_none() -> None:
    """Without any endpoint variable every endpoint property is None."""
    config = Config()

    assert config.endpoint_url is None
    assert config.s3_endpoint_url is None
    assert config.textract_endpoint_url is None
    assert config.bedrock_endpoint_url is None


def test_config_global_endpoint_url_applies_to_all_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AWS_ENDPOINT_URL is the fallback for every service."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")

    config = Config()

    assert config.endpoint_url == "http://localhost:4566"
    assert config.s3_endpoint_url == "http://localhost:4566"
    assert config.textract_endpoint_url == "http://localhost:4566"
    assert config.bedrock_endpoint_url == "http://localhost:4566"


def test_config_per_service_endpoint_urls_override_the_global_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service-specific endpoints win over AWS_ENDPOINT_URL."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setenv("AWS_TEXTRACT_ENDPOINT_URL", "http://localhost:9001")
    monkeypatch.setenv("AWS_BEDROCK_ENDPOINT_URL", "http://localhost:9002")

    config = Config()

    assert config.s3_endpoint_url == "http://localhost:9000"
    assert config.textract_endpoint_url == "http://localhost:9001"
    assert config.bedrock_endpoint_url == "http://localhost:9002"


def test_config_credentials_default_to_none() -> None:
    """Unset credentials leave the default boto3 chain in charge."""
    config = Config()

    assert config.aws_access_key_id is None
    assert config.aws_secret_access_key is None
    assert config.aws_session_token is None
    assert config.has_explicit_credentials is False


def test_config_reads_explicit_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A complete credential set is exposed and reported as explicit."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "FQoGZXIvYXdzEXAMPLESESSIONTOKEN")

    config = Config()

    assert config.aws_access_key_id == "AKIAIOSFODNN7EXAMPLE"
    assert config.aws_secret_access_key == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert config.aws_session_token == "FQoGZXIvYXdzEXAMPLESESSIONTOKEN"
    assert config.has_explicit_credentials is True


@pytest.mark.parametrize(
    "env",
    [
        {"AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE"},
        {"AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"},
        {"AWS_SESSION_TOKEN": "FQoGZXIvYXdzEXAMPLESESSIONTOKEN"},
    ],
)
def test_config_partial_credentials_are_not_explicit(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """An incomplete credential set is not treated as explicit credentials."""
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert Config().has_explicit_credentials is False


def test_config_repr_does_not_expose_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repr'ing the config never prints credential material."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

    text = repr(Config())

    assert text == "Config()"
    assert "AKIAIOSFODNN7EXAMPLE" not in text
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in text
