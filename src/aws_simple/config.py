"""Configuration management via environment variables."""

import os

from dotenv import load_dotenv

from .exceptions import ConfigurationError

# Load .env file if present
load_dotenv()


class Config:
    """Centralized configuration for AWS services."""

    def __repr__(self) -> str:
        """Return a representation that never exposes credential material."""
        return f"{type(self).__name__}()"

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
    def endpoint_url(self) -> str | None:
        """
        Custom endpoint URL applied to every service (optional).

        Set it to talk to an AWS-compatible stack such as LocalStack or MinIO,
        for example ``http://localhost:4566``. Per-service variables override
        this one.
        """
        return self._get_optional("AWS_ENDPOINT_URL")

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
        value = self._get_optional("AWS_SSL_VERIFY", "true") or "true"
        return value.lower() not in ("false", "0", "no", "off")

    # Credentials
    #
    # These are optional: when they are unset the default boto3 credential
    # chain (IAM role, ~/.aws/credentials, instance metadata, ...) is used.
    # SECURITY: never log, print or interpolate these values into an error
    # message.
    @property
    def aws_access_key_id(self) -> str | None:
        """Explicit AWS access key ID (optional). Never log this value."""
        return self._get_optional("AWS_ACCESS_KEY_ID")

    @property
    def aws_secret_access_key(self) -> str | None:
        """Explicit AWS secret access key (optional). Never log this value."""
        return self._get_optional("AWS_SECRET_ACCESS_KEY")

    @property
    def aws_session_token(self) -> str | None:
        """Explicit AWS session token, for temporary credentials (optional)."""
        return self._get_optional("AWS_SESSION_TOKEN")

    @property
    def has_explicit_credentials(self) -> bool:
        """
        Whether a complete explicit credential pair is configured.

        A partial set (only one of the two) is deliberately ignored: handing
        it to boto3 would silently break the default credential chain.
        """
        return bool(self.aws_access_key_id and self.aws_secret_access_key)

    # S3
    @property
    def s3_bucket(self) -> str:
        """Default S3 bucket name."""
        return self._get_required("AWS_S3_BUCKET")

    @property
    def s3_endpoint_url(self) -> str | None:
        """S3 endpoint URL (defaults to endpoint_url)."""
        return self._get_optional("AWS_S3_ENDPOINT_URL") or self.endpoint_url

    # Textract
    @property
    def textract_region(self) -> str:
        """Textract region (defaults to aws_region)."""
        return self._get_optional("AWS_TEXTRACT_REGION") or self.aws_region

    @property
    def textract_endpoint_url(self) -> str | None:
        """Textract endpoint URL (defaults to endpoint_url)."""
        return self._get_optional("AWS_TEXTRACT_ENDPOINT_URL") or self.endpoint_url

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

    @property
    def bedrock_endpoint_url(self) -> str | None:
        """Bedrock Runtime endpoint URL (defaults to endpoint_url)."""
        return self._get_optional("AWS_BEDROCK_ENDPOINT_URL") or self.endpoint_url


# Singleton instance
config = Config()
