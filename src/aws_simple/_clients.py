"""Internal AWS clients factory (not exposed in public API)."""

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from .config import config
from .exceptions import ClientInitializationError


class AWSClients:
    """Factory for creating and caching AWS service clients."""

    _s3_client: Any | None = None
    _textract_client: Any | None = None
    _bedrock_runtime_client: Any | None = None

    @classmethod
    def _get_session_kwargs(cls) -> dict[str, str]:
        """Get boto3 session configuration."""
        kwargs: dict[str, str] = {"region_name": config.aws_region}
        if config.aws_profile:
            kwargs["profile_name"] = config.aws_profile
        return kwargs

    @classmethod
    def get_s3_client(cls) -> Any:
        """Get or create S3 client."""
        if cls._s3_client is None:
            try:
                session = boto3.Session(**cls._get_session_kwargs())
                cls._s3_client = session.client("s3", verify=config.ssl_verify)
            except (BotoCoreError, ClientError, NoCredentialsError) as e:
                raise ClientInitializationError(f"Failed to initialize S3 client: {e}") from e
        return cls._s3_client

    @classmethod
    def get_textract_client(cls) -> Any:
        """Get or create Textract client."""
        if cls._textract_client is None:
            try:
                kwargs = cls._get_session_kwargs()
                kwargs["region_name"] = config.textract_region
                session = boto3.Session(**kwargs)
                cls._textract_client = session.client("textract", verify=config.ssl_verify)
            except (BotoCoreError, ClientError, NoCredentialsError) as e:
                raise ClientInitializationError(f"Failed to initialize Textract client: {e}") from e
        return cls._textract_client

    @classmethod
    def get_bedrock_runtime_client(cls) -> Any:
        """Get or create Bedrock Runtime client."""
        if cls._bedrock_runtime_client is None:
            try:
                kwargs = cls._get_session_kwargs()
                kwargs["region_name"] = config.bedrock_region
                session = boto3.Session(**kwargs)
                cls._bedrock_runtime_client = session.client(
                    "bedrock-runtime", verify=config.ssl_verify
                )
            except (BotoCoreError, ClientError, NoCredentialsError) as e:
                raise ClientInitializationError(f"Failed to initialize Bedrock client: {e}") from e
        return cls._bedrock_runtime_client

    @classmethod
    def reset_clients(cls) -> None:
        """Reset all cached clients (useful for testing)."""
        cls._s3_client = None
        cls._textract_client = None
        cls._bedrock_runtime_client = None
