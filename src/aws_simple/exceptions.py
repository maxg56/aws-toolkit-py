"""Custom exceptions for aws-simple library."""


class AWSSimpleError(Exception):
    """Base exception for all aws-simple errors."""

    pass


class ConfigurationError(AWSSimpleError):
    """Raised when required environment variables are missing or invalid."""

    pass


class S3Error(AWSSimpleError):
    """Raised when S3 operations fail."""

    pass


class TextractError(AWSSimpleError):
    """Raised when Textract operations fail."""

    pass


class BedrockError(AWSSimpleError):
    """Raised when Bedrock operations fail."""

    pass


class ClientInitializationError(AWSSimpleError):
    """Raised when AWS client initialization fails."""

    pass
