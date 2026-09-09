"""Internal AWS clients factory (not exposed in public API)."""

import warnings
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .config import config
from .exceptions import ClientInitializationError, ConfigurationError

# Placeholder substituted for credential material found in an error message.
_REDACTED = "***"


def _sanitize(message: str) -> str:
    """
    Strip any configured credential material out of an error message.

    Botocore errors can embed the credentials they were built with, so every
    message is scrubbed before it reaches ClientInitializationError.
    """
    for secret in (
        config.aws_secret_access_key,
        config.aws_session_token,
        config.aws_access_key_id,
    ):
        if secret:
            message = message.replace(secret, _REDACTED)
    return message


def _is_aws_endpoint(endpoint_url: str | None) -> bool:
    """
    Whether the given endpoint is real AWS.

    ``None`` means no custom endpoint was configured, i.e. the default AWS
    endpoint for the service/region is used.
    """
    if endpoint_url is None:
        return True
    host = urlparse(endpoint_url).hostname or ""
    return host == "amazonaws.com" or host.endswith(".amazonaws.com")


class AWSClients:
    """Factory for creating and caching AWS service clients."""

    _s3_client: Any | None = None
    _textract_client: Any | None = None
    _bedrock_runtime_client: Any | None = None
    _warned_insecure_endpoints: set[str] = set()

    @classmethod
    def _session_kwargs(cls, region_name: str) -> dict[str, Any]:
        """
        Build the keyword arguments for a boto3 session.

        Explicit credentials are only included when both the access key ID and
        the secret access key are set: a partial set would silently break the
        default credential chain.
        """
        kwargs: dict[str, Any] = {"region_name": region_name}
        if config.aws_profile:
            kwargs["profile_name"] = config.aws_profile
        if config.has_explicit_credentials:
            kwargs["aws_access_key_id"] = config.aws_access_key_id
            kwargs["aws_secret_access_key"] = config.aws_secret_access_key
            if config.aws_session_token:
                kwargs["aws_session_token"] = config.aws_session_token
        return kwargs

    @classmethod
    def _build_session(cls, region_name: str) -> boto3.Session:
        """Create a boto3 session for the given region."""
        return boto3.Session(**cls._session_kwargs(region_name))

    @classmethod
    def _botocore_config(cls) -> BotocoreConfig:
        """Build the retry/timeout configuration shared by every client."""
        return BotocoreConfig(
            retries={"max_attempts": config.max_attempts, "mode": config.retry_mode},
            connect_timeout=config.connect_timeout,
            read_timeout=config.read_timeout,
        )

    @classmethod
    def _check_ssl_verify(cls, endpoint_url: str | None) -> None:
        """
        Enforce that SSL verification can only be disabled for a non-AWS endpoint.

        Raises ConfigurationError if verification is disabled for what resolves
        to a real AWS endpoint, and emits a UserWarning (once per endpoint) when
        it is honoured for a custom one.
        """
        if config.ssl_verify:
            return
        if _is_aws_endpoint(endpoint_url):
            raise ConfigurationError(
                "SSL certificate verification cannot be disabled for an AWS "
                f"endpoint ({endpoint_url or 'the default AWS endpoint'}). "
                "AWS_INSECURE_DISABLE_SSL_VERIFY only applies to a custom "
                "endpoint_url (e.g. LocalStack or MinIO)."
            )
        warn_key = endpoint_url or ""
        if warn_key not in cls._warned_insecure_endpoints:
            cls._warned_insecure_endpoints.add(warn_key)
            warnings.warn(
                f"SSL certificate verification is disabled for endpoint {endpoint_url!r}. "
                "Only use this for local development/testing with self-signed certificates.",
                UserWarning,
                stacklevel=3,
            )

    @classmethod
    def _client_kwargs(cls, endpoint_url: str | None) -> dict[str, Any]:
        """Build the keyword arguments for a service client."""
        cls._check_ssl_verify(endpoint_url)
        kwargs: dict[str, Any] = {"verify": config.ssl_verify, "config": cls._botocore_config()}
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        return kwargs

    @classmethod
    def get_s3_client(cls) -> Any:
        """Get or create S3 client."""
        if cls._s3_client is None:
            try:
                session = cls._build_session(config.aws_region)
                cls._s3_client = session.client("s3", **cls._client_kwargs(config.s3_endpoint_url))
            except (BotoCoreError, ClientError, NoCredentialsError) as e:
                raise ClientInitializationError(
                    _sanitize(f"Failed to initialize S3 client: {e}")
                ) from e
        return cls._s3_client

    @classmethod
    def get_textract_client(cls) -> Any:
        """Get or create Textract client."""
        if cls._textract_client is None:
            try:
                session = cls._build_session(config.textract_region)
                cls._textract_client = session.client(
                    "textract", **cls._client_kwargs(config.textract_endpoint_url)
                )
            except (BotoCoreError, ClientError, NoCredentialsError) as e:
                raise ClientInitializationError(
                    _sanitize(f"Failed to initialize Textract client: {e}")
                ) from e
        return cls._textract_client

    @classmethod
    def get_bedrock_runtime_client(cls) -> Any:
        """Get or create Bedrock Runtime client."""
        if cls._bedrock_runtime_client is None:
            try:
                session = cls._build_session(config.bedrock_region)
                cls._bedrock_runtime_client = session.client(
                    "bedrock-runtime", **cls._client_kwargs(config.bedrock_endpoint_url)
                )
            except (BotoCoreError, ClientError, NoCredentialsError) as e:
                raise ClientInitializationError(
                    _sanitize(f"Failed to initialize Bedrock client: {e}")
                ) from e
        return cls._bedrock_runtime_client

    @classmethod
    def reset_clients(cls) -> None:
        """Reset all cached clients (useful for testing, and after configure())."""
        cls._s3_client = None
        cls._textract_client = None
        cls._bedrock_runtime_client = None
        cls._warned_insecure_endpoints = set()
