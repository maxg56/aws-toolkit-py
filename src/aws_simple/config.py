"""Configuration management via environment variables and ``configure()``."""

import os
from collections.abc import Mapping
from typing import Final

from dotenv import load_dotenv

from .exceptions import ConfigurationError

# Load .env file if present
load_dotenv()


# Declarative registry of the settings ``configure()`` accepts: each keyword
# maps to the environment variable it overrides. Adding a new setting means
# adding one entry here plus the matching keyword-only parameter on
# ``configure()`` — nothing else in this module needs to change.
SETTING_ENV_VARS: Final[Mapping[str, str]] = {
    "region": "AWS_REGION",
    "profile": "AWS_PROFILE",
    "bucket": "AWS_S3_BUCKET",
    "endpoint_url": "AWS_ENDPOINT_URL",
    "s3_endpoint_url": "AWS_S3_ENDPOINT_URL",
    "textract_region": "AWS_TEXTRACT_REGION",
    "textract_endpoint_url": "AWS_TEXTRACT_ENDPOINT_URL",
    "bedrock_region": "AWS_BEDROCK_REGION",
    "bedrock_endpoint_url": "AWS_BEDROCK_ENDPOINT_URL",
    "bedrock_model_id": "AWS_BEDROCK_MODEL_ID",
    "aws_access_key_id": "AWS_ACCESS_KEY_ID",
    "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
    "aws_session_token": "AWS_SESSION_TOKEN",
}


def _invalidate_clients() -> None:
    """
    Drop the cached AWS clients so the next call rebuilds them.

    Imported lazily: ``_clients`` imports this module, and the cache must be
    invalidated on *every* configuration mutation, not only when the caller
    remembers to do it.
    """
    from ._clients import AWSClients

    AWSClients.reset_clients()


class Config:
    """
    Centralized configuration for AWS services.

    Values are resolved with an explicit precedence:

    1. programmatic overrides set through :func:`configure`
    2. environment variables
    3. variables loaded from a ``.env`` file
    4. the built-in defaults

    Overrides live on the instance, so mutating one instance never leaks into
    another (which keeps tests isolated).
    """

    def __init__(self) -> None:
        """Create a config with no programmatic override applied."""
        # Keyed by environment variable name, so lookups stay a single dict hit
        # in _get_optional/_get_required.
        self._overrides: dict[str, str] = {}

    def __repr__(self) -> str:
        """Return a representation that never exposes credential material."""
        return f"{type(self).__name__}()"

    # Programmatic configuration
    def set_overrides(self, settings: Mapping[str, str]) -> None:
        """
        Apply programmatic overrides and invalidate the cached clients.

        Args:
            settings: Mapping of :data:`SETTING_ENV_VARS` keys to values.

        Raises:
            ConfigurationError: If a setting is unknown or is not a string.

        SECURITY: values may be credential material, so neither the validation
        nor the resulting error messages ever include them.
        """
        unknown = sorted(set(settings) - set(SETTING_ENV_VARS))
        if unknown:
            raise ConfigurationError(
                f"Unknown configuration setting(s): {', '.join(unknown)}. "
                f"Supported settings: {', '.join(sorted(SETTING_ENV_VARS))}."
            )
        for name, value in settings.items():
            if not isinstance(value, str):
                raise ConfigurationError(f"Configuration setting '{name}' must be a string.")
        for name, value in settings.items():
            self._overrides[SETTING_ENV_VARS[name]] = value
        _invalidate_clients()

    def clear_overrides(self) -> None:
        """Drop every programmatic override and invalidate the cached clients."""
        self._overrides.clear()
        _invalidate_clients()

    def _get_required(self, key: str) -> str:
        """Get a required setting from the overrides or the environment."""
        value = self._overrides.get(key) or os.getenv(key)
        if not value:
            raise ConfigurationError(
                f"Missing required environment variable: {key}. "
                f"Please set it in your environment or .env file, "
                f"or pass it to configure()."
            )
        return value

    def _get_optional(self, key: str, default: str | None = None) -> str | None:
        """Get an optional setting from the overrides or the environment."""
        if key in self._overrides:
            return self._overrides[key]
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


def configure(
    *,
    region: str | None = None,
    profile: str | None = None,
    bucket: str | None = None,
    endpoint_url: str | None = None,
    s3_endpoint_url: str | None = None,
    textract_region: str | None = None,
    textract_endpoint_url: str | None = None,
    bedrock_region: str | None = None,
    bedrock_endpoint_url: str | None = None,
    bedrock_model_id: str | None = None,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
) -> None:
    """
    Configure the library from code, overriding the environment.

    Every argument is optional and keyword-only; the ones left out (or passed
    as ``None``) are untouched, so successive calls accumulate. Values set here
    win over environment variables, which win over a ``.env`` file. Call
    :func:`reset_configuration` to drop the overrides and fall back to the
    environment again.

    The cached AWS clients are invalidated on every call, so a change always
    takes effect on the next operation — even one made after a client was
    already built.

    Example:
        >>> from aws_simple import configure
        >>> configure(region="eu-west-3", bucket="my-bucket",
        ...           endpoint_url="http://localhost:4566")

    Args:
        region: Default AWS region for every service.
        profile: Named AWS profile to build the boto3 session with.
        bucket: Default S3 bucket.
        endpoint_url: Custom endpoint applied to every service.
        s3_endpoint_url: S3-specific endpoint (defaults to ``endpoint_url``).
        textract_region: Textract-specific region (defaults to ``region``).
        textract_endpoint_url: Textract endpoint (defaults to ``endpoint_url``).
        bedrock_region: Bedrock-specific region (defaults to ``region``).
        bedrock_endpoint_url: Bedrock endpoint (defaults to ``endpoint_url``).
        bedrock_model_id: Default Bedrock model ID.
        aws_access_key_id: Explicit access key ID. Never logged.
        aws_secret_access_key: Explicit secret access key. Never logged.
        aws_session_token: Explicit session token, for temporary credentials.

    Raises:
        ConfigurationError: If a value is not a string.

    SECURITY: credentials passed here are held in memory only. Like their
    environment counterparts they are never logged, never part of a ``Config``
    repr, and are scrubbed out of client initialization errors.
    """
    # locals() is read as the first statement so it holds exactly the
    # parameters above: one signature, no third list of setting names to keep
    # in sync.
    settings = {name: value for name, value in locals().items() if value is not None}
    config.set_overrides(settings)


def reset_configuration() -> None:
    """
    Drop every value set through :func:`configure`.

    Configuration falls back to the environment (and ``.env``), and the cached
    AWS clients are invalidated so the next call rebuilds them.
    """
    config.clear_overrides()
