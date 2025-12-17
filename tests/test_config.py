"""Tests for config module."""

import pytest

from aws_simple.config import Config
from aws_simple.exceptions import ConfigurationError


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
