"""Configuration management via environment variables."""

import os

from dotenv import load_dotenv

from .exceptions import ConfigurationError

# Load .env file if present
load_dotenv()


class Config:
    """Centralized configuration for AWS services."""

    @staticmethod
    def _get_required(key: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(key)
        if not value:
            raise ConfigurationError(
                f"Missing required environment variable: {key}. "
                f"Please set it in your environment or .env file."
            )
        return value

    @staticmethod
    def _get_optional(key: str, default: str | None = None) -> str | None:
        """Get optional environment variable with default."""
        return os.getenv(key, default)

    # AWS General
    @property
    def aws_region(self) -> str:
        """AWS region (default: us-east-1)."""
        return self._get_optional("AWS_REGION", "us-east-1") or "us-east-1"

    @property
    def aws_profile(self) -> str | None:
        """AWS profile name (optional, for local development)."""
        return self._get_optional("AWS_PROFILE")

    @property
    def ssl_verify(self) -> bool:
        """
        SSL certificate verification flag (default: True).

        WARNING: Disabling SSL certificate verification is insecure and can
        expose you to man-in-the-middle (MITM) attacks. Only set this to
        False in controlled development or testing environments, for example
        when working with self-signed certificates.

        This is controlled via the AWS_SSL_VERIFY environment variable; any of
        "false", "0", "no", or "off" (case-insensitive) will disable
        verification.
        """
        # NOTE: Only disable SSL verification for local development/testing
        # with self-signed certificates. Do NOT disable it in production.
        value = self._get_optional("AWS_SSL_VERIFY", "true")
        return value.lower() not in ("false", "0", "no", "off")

    # S3
    @property
    def s3_bucket(self) -> str:
        """Default S3 bucket name."""
        return self._get_required("AWS_S3_BUCKET")

    # Textract
    @property
    def textract_region(self) -> str:
        """Textract region (defaults to aws_region)."""
        return self._get_optional("AWS_TEXTRACT_REGION") or self.aws_region

    # Bedrock
    @property
    def bedrock_model_id(self) -> str:
        """Default Bedrock model ID."""
        return (
            self._get_optional("AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
            or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

    @property
    def bedrock_region(self) -> str:
        """Bedrock region (defaults to aws_region)."""
        return self._get_optional("AWS_BEDROCK_REGION") or self.aws_region


# Singleton instance
config = Config()
