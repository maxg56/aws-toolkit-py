"""Configuration management via environment variables and configure()."""

import os
import warnings
from typing import Any, Literal, cast

from dotenv import load_dotenv

from .exceptions import ConfigurationError

# Load .env file if present
load_dotenv()

RetryMode = Literal["legacy", "standard", "adaptive"]
_RETRY_MODES: tuple[RetryMode, ...] = ("legacy", "standard", "adaptive")


class Config:
    """Centralized configuration for AWS services."""

    def __init__(self) -> None:
        # Programmatic overrides set via configure(); take precedence over
        # environment variables and any .env file.
        self._overrides: dict[str, Any] = {}

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
        return (
            self._overrides.get("aws_region")
            or self._get_optional("AWS_REGION", "us-east-1")
            or ("us-east-1")
        )

    @property
    def aws_profile(self) -> str | None:
        """AWS profile name (optional, for local development)."""
        return self._overrides.get("aws_profile") or self._get_optional("AWS_PROFILE")

    @property
    def endpoint_url(self) -> str | None:
        """
        Custom endpoint URL applied to every service (optional).

        Set it to talk to an AWS-compatible stack such as LocalStack or MinIO,
        for example ``http://localhost:4566``. Per-service variables override
        this one.
        """
        return self._overrides.get("endpoint_url") or self._get_optional("AWS_ENDPOINT_URL")

    @property
    def ssl_verify(self) -> bool:
        """
        SSL certificate verification flag (default: True).

        WARNING: Disabling SSL certificate verification is insecure and can
        expose you to man-in-the-middle (MITM) attacks. Only set this to
        False in controlled development or testing environments, for example
        when working with self-signed certificates.

        Controlled via the ``AWS_INSECURE_DISABLE_SSL_VERIFY`` environment
        variable; any of "true", "1", "yes", or "on" (case-insensitive) will
        disable verification. The legacy ``AWS_SSL_VERIFY`` name still works
        for now (with the opposite polarity — "false" disables verification)
        but emits a ``DeprecationWarning``.

        This flag can never disable verification against a real AWS endpoint
        (``AWSClients`` enforces that) — it only has an effect for a custom
        ``endpoint_url`` such as LocalStack or MinIO.
        """
        value = self._get_optional("AWS_INSECURE_DISABLE_SSL_VERIFY")
        if value is not None:
            return value.lower() not in ("true", "1", "yes", "on")

        legacy_value = self._get_optional("AWS_SSL_VERIFY")
        if legacy_value is not None:
            warnings.warn(
                "AWS_SSL_VERIFY is deprecated and will be removed in a future "
                "release; use AWS_INSECURE_DISABLE_SSL_VERIFY instead (note the "
                "inverted polarity: AWS_INSECURE_DISABLE_SSL_VERIFY=true disables "
                "verification, where AWS_SSL_VERIFY=false used to).",
                DeprecationWarning,
                stacklevel=2,
            )
            return legacy_value.lower() not in ("false", "0", "no", "off")

        return True

    # Credentials
    #
    # These are optional: when they are unset the default boto3 credential
    # chain (IAM role, ~/.aws/credentials, instance metadata, ...) is used.
    # SECURITY: never log, print or interpolate these values into an error
    # message.
    @property
    def aws_access_key_id(self) -> str | None:
        """Explicit AWS access key ID (optional). Never log this value."""
        return self._overrides.get("aws_access_key_id") or self._get_optional("AWS_ACCESS_KEY_ID")

    @property
    def aws_secret_access_key(self) -> str | None:
        """Explicit AWS secret access key (optional). Never log this value."""
        return self._overrides.get("aws_secret_access_key") or self._get_optional(
            "AWS_SECRET_ACCESS_KEY"
        )

    @property
    def aws_session_token(self) -> str | None:
        """Explicit AWS session token, for temporary credentials (optional)."""
        return self._overrides.get("aws_session_token") or self._get_optional("AWS_SESSION_TOKEN")

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
        return self._overrides.get("s3_bucket") or self._get_required("AWS_S3_BUCKET")

    @property
    def s3_endpoint_url(self) -> str | None:
        """S3 endpoint URL (defaults to endpoint_url)."""
        return (
            self._overrides.get("s3_endpoint_url")
            or self._get_optional("AWS_S3_ENDPOINT_URL")
            or self.endpoint_url
        )

    # Textract
    @property
    def textract_region(self) -> str:
        """Textract region (defaults to aws_region)."""
        return (
            self._overrides.get("textract_region")
            or self._get_optional("AWS_TEXTRACT_REGION")
            or self.aws_region
        )

    @property
    def textract_endpoint_url(self) -> str | None:
        """Textract endpoint URL (defaults to endpoint_url)."""
        return (
            self._overrides.get("textract_endpoint_url")
            or self._get_optional("AWS_TEXTRACT_ENDPOINT_URL")
            or self.endpoint_url
        )

    # Bedrock
    @property
    def bedrock_model_id(self) -> str:
        """Default Bedrock model ID."""
        return (
            self._overrides.get("bedrock_model_id")
            or self._get_optional(
                "AWS_BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
            )
            or "anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

    @property
    def bedrock_region(self) -> str:
        """Bedrock region (defaults to aws_region)."""
        return (
            self._overrides.get("bedrock_region")
            or self._get_optional("AWS_BEDROCK_REGION")
            or self.aws_region
        )

    @property
    def bedrock_endpoint_url(self) -> str | None:
        """Bedrock Runtime endpoint URL (defaults to endpoint_url)."""
        return (
            self._overrides.get("bedrock_endpoint_url")
            or self._get_optional("AWS_BEDROCK_ENDPOINT_URL")
            or self.endpoint_url
        )

    # Retry / timeout (botocore Config)
    @property
    def max_attempts(self) -> int:
        """Maximum number of retry attempts per request (default: 3)."""
        override = self._overrides.get("max_attempts")
        if override is not None:
            return int(override)
        return int(self._get_optional("AWS_MAX_ATTEMPTS", "3") or "3")

    @property
    def retry_mode(self) -> RetryMode:
        """Botocore retry mode: "legacy", "standard" or "adaptive" (default: "standard")."""
        value = (
            self._overrides.get("retry_mode")
            or self._get_optional("AWS_RETRY_MODE", "standard")
            or "standard"
        )
        if value not in _RETRY_MODES:
            raise ConfigurationError(
                f"Invalid AWS_RETRY_MODE: {value!r}. Must be one of: " f"{', '.join(_RETRY_MODES)}."
            )
        return cast(RetryMode, value)

    @property
    def connect_timeout(self) -> float:
        """Connection timeout in seconds (default: 10)."""
        override = self._overrides.get("connect_timeout")
        if override is not None:
            return float(override)
        return float(self._get_optional("AWS_CONNECT_TIMEOUT", "10") or "10")

    @property
    def read_timeout(self) -> float:
        """Read timeout in seconds (default: 60)."""
        override = self._overrides.get("read_timeout")
        if override is not None:
            return float(override)
        return float(self._get_optional("AWS_READ_TIMEOUT", "60") or "60")


# Singleton instance
config = Config()


def configure(
    *,
    region: str | None = None,
    profile: str | None = None,
    endpoint_url: str | None = None,
    bucket: str | None = None,
    s3_endpoint_url: str | None = None,
    textract_region: str | None = None,
    textract_endpoint_url: str | None = None,
    bedrock_region: str | None = None,
    bedrock_endpoint_url: str | None = None,
    bedrock_model_id: str | None = None,
    access_key_id: str | None = None,
    secret_access_key: str | None = None,
    session_token: str | None = None,
    max_attempts: int | None = None,
    retry_mode: str | None = None,
    connect_timeout: float | None = None,
    read_timeout: float | None = None,
) -> None:
    """
    Programmatically override configuration.

    A value passed here takes precedence over the matching environment
    variable (and any ``.env`` file) until the process exits or ``configure()``
    is called again. Omitting a parameter (leaving it ``None``) leaves
    whatever was configured before — by an earlier ``configure()`` call or by
    the environment — unchanged.

    Calling this resets every cached AWS client, so the very next S3,
    Textract or Bedrock call is built from the new settings:

        >>> from aws_simple import configure
        >>> configure(region="eu-west-3", bucket="my-bucket")

    A per-call region/bucket override on the service functions themselves is
    out of scope: ``configure()`` is the supported way to change settings,
    including for multi-region use — call it again before the calls that need
    the other region.
    """
    overrides = {
        "aws_region": region,
        "aws_profile": profile,
        "endpoint_url": endpoint_url,
        "s3_bucket": bucket,
        "s3_endpoint_url": s3_endpoint_url,
        "textract_region": textract_region,
        "textract_endpoint_url": textract_endpoint_url,
        "bedrock_region": bedrock_region,
        "bedrock_endpoint_url": bedrock_endpoint_url,
        "bedrock_model_id": bedrock_model_id,
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "aws_session_token": session_token,
        "max_attempts": max_attempts,
        "retry_mode": retry_mode,
        "connect_timeout": connect_timeout,
        "read_timeout": read_timeout,
    }
    config._overrides.update({key: value for key, value in overrides.items() if value is not None})

    # Imported lazily: _clients imports `config` from this module at module
    # load time, so importing it back at the top would be circular.
    from ._clients import AWSClients

    AWSClients.reset_clients()
