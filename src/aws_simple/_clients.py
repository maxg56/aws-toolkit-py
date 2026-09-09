"""Internal AWS clients factory (not exposed in public API)."""

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .config import config
from .exceptions import ClientInitializationError

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


class AWSClients:
    """Factory for creating and caching AWS service clients."""

    _s3_client: Any | None = None
    _textract_client: Any | None = None
    _bedrock_runtime_client: Any | None = None

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
    def _client_kwargs(cls, endpoint_url: str | None) -> dict[str, Any]:
        """Build the keyword arguments for a service client."""
        kwargs: dict[str, Any] = {"verify": config.ssl_verify}
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
        """
        Drop every cached client so the next call rebuilds them.

        This is the cache-invalidation hook: ``configure()`` (and any other
        configuration mutation) calls it, which is what makes a configuration
        change apply to calls made after a client was already built.
        """
        cls._s3_client = None
        cls._textract_client = None
        cls._bedrock_runtime_client = None
