"""Tests for the internal AWS client factory."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from aws_simple._clients import AWSClients
from aws_simple.exceptions import ClientInitializationError

EXPECTED_TWO = 2


# ---------------------------------------------------------------------------
# session kwargs
# ---------------------------------------------------------------------------


def test_get_session_kwargs_without_profile(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without AWS_PROFILE only the region is passed to boto3.Session."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_REGION", "eu-west-3")

    assert AWSClients._get_session_kwargs() == {"region_name": "eu-west-3"}


def test_get_session_kwargs_with_profile(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_PROFILE is forwarded as profile_name when set."""
    monkeypatch.setenv("AWS_PROFILE", "dev-profile")
    monkeypatch.setenv("AWS_REGION", "eu-west-3")

    assert AWSClients._get_session_kwargs() == {
        "region_name": "eu-west-3",
        "profile_name": "dev-profile",
    }


def test_s3_client_uses_profile_from_env(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The profile ends up in the boto3.Session call for the S3 client."""
    monkeypatch.setenv("AWS_PROFILE", "prod-profile")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    assert mock_session.call_args.kwargs["profile_name"] == "prod-profile"


# ---------------------------------------------------------------------------
# client creation
# ---------------------------------------------------------------------------


def test_get_s3_client_creates_client_with_region_and_ssl(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The S3 client is built from the generic AWS region with SSL verify on."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-west-2")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        expected = mock_session.return_value.client.return_value

        client = AWSClients.get_s3_client()

    assert client is expected
    mock_session.assert_called_once_with(region_name="us-west-2")
    mock_session.return_value.client.assert_called_once_with("s3", verify=True)


def test_get_textract_client_uses_textract_region(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_TEXTRACT_REGION overrides the generic region for Textract."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_TEXTRACT_REGION", "eu-central-1")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_textract_client()

    mock_session.assert_called_once_with(region_name="eu-central-1")
    mock_session.return_value.client.assert_called_once_with("textract", verify=True)


def test_get_bedrock_runtime_client_uses_bedrock_region(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_BEDROCK_REGION overrides the generic region for Bedrock."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_BEDROCK_REGION", "ap-southeast-2")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_bedrock_runtime_client()

    mock_session.assert_called_once_with(region_name="ap-southeast-2")
    mock_session.return_value.client.assert_called_once_with("bedrock-runtime", verify=True)


def test_ssl_verify_can_be_disabled(reset_clients: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """AWS_SSL_VERIFY=false disables certificate verification on the client."""
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    assert mock_session.return_value.client.call_args.kwargs["verify"] is False


# ---------------------------------------------------------------------------
# caching / reset
# ---------------------------------------------------------------------------


def test_clients_are_cached(reset_clients: None) -> None:
    """Each client is created once and reused on subsequent calls."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        first = AWSClients.get_s3_client()
        second = AWSClients.get_s3_client()

    assert first is second
    assert mock_session.call_count == 1


def test_textract_client_is_cached(reset_clients: None) -> None:
    """The Textract client is created once and reused."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        first = AWSClients.get_textract_client()
        second = AWSClients.get_textract_client()

    assert first is second
    assert mock_session.call_count == 1


def test_bedrock_client_is_cached(reset_clients: None) -> None:
    """The Bedrock Runtime client is created once and reused."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        first = AWSClients.get_bedrock_runtime_client()
        second = AWSClients.get_bedrock_runtime_client()

    assert first is second
    assert mock_session.call_count == 1


def test_each_service_creates_its_own_session(reset_clients: None) -> None:
    """S3, Textract and Bedrock clients are cached independently."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()
        AWSClients.get_textract_client()
        AWSClients.get_bedrock_runtime_client()
        AWSClients.get_s3_client()

    services = [call.args[0] for call in mock_session.return_value.client.call_args_list]
    assert services == ["s3", "textract", "bedrock-runtime"]


def test_reset_clients_forces_recreation(reset_clients: None) -> None:
    """reset_clients() clears the cache so a new client is built."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.return_value.client.side_effect = [MagicMock(), MagicMock()]

        first = AWSClients.get_s3_client()
        AWSClients.reset_clients()
        second = AWSClients.get_s3_client()

    assert first is not second
    assert mock_session.call_count == EXPECTED_TWO


def test_reset_clients_clears_all_services(reset_clients: None) -> None:
    """reset_clients() nulls every cached client, not just S3."""
    with patch("aws_simple._clients.boto3.Session"):
        AWSClients.get_s3_client()
        AWSClients.get_textract_client()
        AWSClients.get_bedrock_runtime_client()

    AWSClients.reset_clients()

    assert AWSClients._s3_client is None
    assert AWSClients._textract_client is None
    assert AWSClients._bedrock_runtime_client is None


# ---------------------------------------------------------------------------
# initialization errors
# ---------------------------------------------------------------------------


def test_get_s3_client_wraps_no_credentials_error(reset_clients: None) -> None:
    """Missing credentials surface as ClientInitializationError."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.return_value.client.side_effect = NoCredentialsError()

        with pytest.raises(
            ClientInitializationError, match="Failed to initialize S3 client"
        ) as exc_info:
            AWSClients.get_s3_client()

    assert isinstance(exc_info.value.__cause__, NoCredentialsError)
    assert AWSClients._s3_client is None


def test_get_textract_client_wraps_botocore_error(reset_clients: None) -> None:
    """BotoCoreError during Textract client creation is wrapped."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.side_effect = BotoCoreError()

        with pytest.raises(
            ClientInitializationError, match="Failed to initialize Textract client"
        ) as exc_info:
            AWSClients.get_textract_client()

    assert isinstance(exc_info.value.__cause__, BotoCoreError)
    assert AWSClients._textract_client is None


def test_get_bedrock_runtime_client_wraps_client_error(reset_clients: None) -> None:
    """ClientError during Bedrock client creation is wrapped."""
    error = ClientError(
        {"Error": {"Code": "UnrecognizedClientException", "Message": "bad token"}},
        "CreateClient",
    )

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.return_value.client.side_effect = error

        with pytest.raises(
            ClientInitializationError, match="Failed to initialize Bedrock client"
        ) as exc_info:
            AWSClients.get_bedrock_runtime_client()

    assert exc_info.value.__cause__ is error
    assert AWSClients._bedrock_runtime_client is None


def test_unexpected_error_is_not_wrapped(reset_clients: None) -> None:
    """Errors outside the boto3 error hierarchy propagate unchanged."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            AWSClients.get_s3_client()
