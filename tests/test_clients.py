"""Tests for the internal AWS client factory."""

import warnings
from collections.abc import Callable
from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest
from botocore.config import Config as BotocoreConfig
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from aws_simple._clients import AWSClients
from aws_simple.exceptions import ClientInitializationError, ConfigurationError

EXPECTED_TWO = 2
EXPECTED_THREE = 3

# Fake credential material — never real keys, only used to assert plumbing
# and that nothing leaks into error messages.
FAKE_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
FAKE_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
FAKE_SESSION_TOKEN = "FQoGZXIvYXdzEXAMPLESESSIONTOKEN"


# ---------------------------------------------------------------------------
# session kwargs
# ---------------------------------------------------------------------------


def test_build_session_without_profile(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without AWS_PROFILE only the region is passed to boto3.Session."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients._build_session("eu-west-3")

    mock_session.assert_called_once_with(region_name="eu-west-3")


def test_build_session_with_profile(reset_clients: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """AWS_PROFILE is forwarded as profile_name when set."""
    monkeypatch.setenv("AWS_PROFILE", "dev-profile")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients._build_session("eu-west-3")

    mock_session.assert_called_once_with(region_name="eu-west-3", profile_name="dev-profile")


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
    mock_session.return_value.client.assert_called_once_with("s3", verify=True, config=ANY)


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
    mock_session.return_value.client.assert_called_once_with("textract", verify=True, config=ANY)


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
    mock_session.return_value.client.assert_called_once_with(
        "bedrock-runtime", verify=True, config=ANY
    )


def test_ssl_verify_can_be_disabled_for_a_custom_endpoint(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_SSL_VERIFY=false disables certificate verification for a non-AWS endpoint."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://localhost:4566")
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")

    with pytest.warns(UserWarning, match="SSL certificate verification is disabled"):
        with patch("aws_simple._clients.boto3.Session") as mock_session:
            AWSClients.get_s3_client()

    assert mock_session.return_value.client.call_args.kwargs["verify"] is False


def test_ssl_verify_disabled_against_default_aws_endpoint_raises(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a custom endpoint, disabling verification targets real AWS and is refused."""
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")

    with patch("aws_simple._clients.boto3.Session"):
        with pytest.raises(ConfigurationError, match="cannot be disabled for an AWS endpoint"):
            AWSClients.get_s3_client()


@pytest.mark.parametrize(
    "endpoint_url",
    ["https://s3.amazonaws.com", "https://bucket.s3.us-east-1.amazonaws.com"],
)
def test_ssl_verify_disabled_against_amazonaws_endpoint_raises(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch, endpoint_url: str
) -> None:
    """An explicit *.amazonaws.com endpoint is still treated as real AWS."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", endpoint_url)
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")

    with patch("aws_simple._clients.boto3.Session"):
        with pytest.raises(ConfigurationError, match="cannot be disabled for an AWS endpoint"):
            AWSClients.get_s3_client()


def test_ssl_verify_warning_is_emitted_once_per_endpoint(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The insecure-endpoint warning does not repeat for every client built
    against the same endpoint (S3, Textract and Bedrock all share it here).
    """
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://localhost:4566")
    monkeypatch.setenv("AWS_INSECURE_DISABLE_SSL_VERIFY", "true")

    with patch("aws_simple._clients.boto3.Session"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            AWSClients.get_s3_client()
            AWSClients.get_textract_client()
            AWSClients.get_bedrock_runtime_client()

    insecure_warnings = [w for w in caught if "SSL certificate verification" in str(w.message)]
    assert len(insecure_warnings) == 1


def test_legacy_ssl_verify_env_var_still_works_with_deprecation_warning(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_SSL_VERIFY is deprecated but still honoured, with a DeprecationWarning."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://localhost:4566")
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")

    with pytest.warns(DeprecationWarning, match="AWS_SSL_VERIFY is deprecated"):
        with patch("aws_simple._clients.boto3.Session") as mock_session:
            AWSClients.get_s3_client()

    assert mock_session.return_value.client.call_args.kwargs["verify"] is False


def test_new_ssl_verify_env_var_takes_precedence_over_legacy(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_INSECURE_DISABLE_SSL_VERIFY wins over the legacy AWS_SSL_VERIFY."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://localhost:4566")
    # Legacy var alone would disable verification ("false" == disable)...
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")
    # ...but the new var explicitly says not to, and must win.
    monkeypatch.setenv("AWS_INSECURE_DISABLE_SSL_VERIFY", "false")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    assert mock_session.return_value.client.call_args.kwargs["verify"] is True


# ---------------------------------------------------------------------------
# retry / timeout configuration (botocore Config)
# ---------------------------------------------------------------------------


def test_default_botocore_config(reset_clients: None) -> None:
    """Without overrides, retries/timeouts use the documented defaults."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    botocore_config = mock_session.return_value.client.call_args.kwargs["config"]
    assert isinstance(botocore_config, BotocoreConfig)
    assert botocore_config.retries == {"max_attempts": 3, "mode": "standard"}
    assert botocore_config.connect_timeout == 10
    assert botocore_config.read_timeout == 60


def test_botocore_config_is_overridable_via_env(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retry/timeout env vars flow into the botocore Config handed to boto3."""
    monkeypatch.setenv("AWS_MAX_ATTEMPTS", "5")
    monkeypatch.setenv("AWS_RETRY_MODE", "adaptive")
    monkeypatch.setenv("AWS_CONNECT_TIMEOUT", "3")
    monkeypatch.setenv("AWS_READ_TIMEOUT", "120")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    botocore_config = mock_session.return_value.client.call_args.kwargs["config"]
    assert botocore_config.retries == {"max_attempts": 5, "mode": "adaptive"}
    assert botocore_config.connect_timeout == 3
    assert botocore_config.read_timeout == 120


def test_botocore_config_is_passed_to_every_service(reset_clients: None) -> None:
    """S3, Textract and Bedrock all receive the same botocore Config."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()
        AWSClients.get_textract_client()
        AWSClients.get_bedrock_runtime_client()

    for call in mock_session.return_value.client.call_args_list:
        assert isinstance(call.kwargs["config"], BotocoreConfig)


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


# ---------------------------------------------------------------------------
# explicit credentials
# ---------------------------------------------------------------------------


def test_explicit_credentials_are_forwarded(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A complete key pair is handed to boto3.Session."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", FAKE_ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", FAKE_SECRET_KEY)

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients._build_session("eu-west-3")

    mock_session.assert_called_once_with(
        region_name="eu-west-3",
        aws_access_key_id=FAKE_ACCESS_KEY,
        aws_secret_access_key=FAKE_SECRET_KEY,
    )


def test_session_token_is_forwarded_with_the_key_pair(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AWS_SESSION_TOKEN completes the temporary-credential triplet."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", FAKE_ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", FAKE_SECRET_KEY)
    monkeypatch.setenv("AWS_SESSION_TOKEN", FAKE_SESSION_TOKEN)

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients._build_session("eu-west-3")

    assert mock_session.call_args.kwargs["aws_session_token"] == FAKE_SESSION_TOKEN


def test_session_token_alone_is_ignored(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session token without a key pair never reaches boto3."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_SESSION_TOKEN", FAKE_SESSION_TOKEN)

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients._build_session("eu-west-3")

    mock_session.assert_called_once_with(region_name="eu-west-3")


@pytest.mark.parametrize(
    "env",
    [
        {"AWS_ACCESS_KEY_ID": FAKE_ACCESS_KEY},
        {"AWS_SECRET_ACCESS_KEY": FAKE_SECRET_KEY},
    ],
)
def test_partial_credentials_fall_back_to_the_default_chain(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    """Half a key pair is ignored so the default credential chain still works."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients._build_session("eu-west-3")

    mock_session.assert_called_once_with(region_name="eu-west-3")


def test_credentials_and_profile_are_both_forwarded(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit key pair does not suppress the configured profile."""
    monkeypatch.setenv("AWS_PROFILE", "dev-profile")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", FAKE_ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", FAKE_SECRET_KEY)

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    kwargs = mock_session.call_args.kwargs
    assert kwargs["profile_name"] == "dev-profile"
    assert kwargs["aws_access_key_id"] == FAKE_ACCESS_KEY


# ---------------------------------------------------------------------------
# endpoint_url
# ---------------------------------------------------------------------------


def test_no_endpoint_url_by_default(reset_clients: None) -> None:
    """Without configuration no endpoint_url kwarg is sent to boto3."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    assert "endpoint_url" not in mock_session.return_value.client.call_args.kwargs


@pytest.mark.parametrize(
    ("getter", "service"),
    [
        (AWSClients.get_s3_client, "s3"),
        (AWSClients.get_textract_client, "textract"),
        (AWSClients.get_bedrock_runtime_client, "bedrock-runtime"),
    ],
)
def test_global_endpoint_url_applies_to_every_service(
    reset_clients: None,
    monkeypatch: pytest.MonkeyPatch,
    getter: Callable[[], Any],
    service: str,
) -> None:
    """AWS_ENDPOINT_URL is honoured by S3, Textract and Bedrock."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        getter()

    mock_session.return_value.client.assert_called_once_with(
        service, verify=True, config=ANY, endpoint_url="http://localhost:4566"
    )


@pytest.mark.parametrize(
    ("env_var", "getter", "service"),
    [
        ("AWS_S3_ENDPOINT_URL", AWSClients.get_s3_client, "s3"),
        ("AWS_TEXTRACT_ENDPOINT_URL", AWSClients.get_textract_client, "textract"),
        ("AWS_BEDROCK_ENDPOINT_URL", AWSClients.get_bedrock_runtime_client, "bedrock-runtime"),
    ],
)
def test_per_service_endpoint_url_overrides_the_global_one(
    reset_clients: None,
    monkeypatch: pytest.MonkeyPatch,
    env_var: str,
    getter: Callable[[], Any],
    service: str,
) -> None:
    """A service-specific endpoint wins over AWS_ENDPOINT_URL."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv(env_var, "http://localhost:9000")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        getter()

    mock_session.return_value.client.assert_called_once_with(
        service, verify=True, config=ANY, endpoint_url="http://localhost:9000"
    )


def test_endpoint_url_combines_with_disabled_ssl_verify(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-signed local endpoint can be used with verification disabled."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://localhost:4566")
    monkeypatch.setenv("AWS_SSL_VERIFY", "false")

    with pytest.warns(UserWarning):
        with patch("aws_simple._clients.boto3.Session") as mock_session:
            AWSClients.get_s3_client()

    mock_session.return_value.client.assert_called_once_with(
        "s3", verify=False, config=ANY, endpoint_url="https://localhost:4566"
    )


# ---------------------------------------------------------------------------
# credential leakage
# ---------------------------------------------------------------------------


def test_error_message_never_leaks_credentials(
    reset_clients: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A botocore error quoting the credentials is not re-raised verbatim."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", FAKE_ACCESS_KEY)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", FAKE_SECRET_KEY)
    monkeypatch.setenv("AWS_SESSION_TOKEN", FAKE_SESSION_TOKEN)

    error = ClientError(
        {
            "Error": {
                "Code": "InvalidClientTokenId",
                "Message": (
                    f"key={FAKE_ACCESS_KEY} secret={FAKE_SECRET_KEY} "
                    f"token={FAKE_SESSION_TOKEN} was rejected"
                ),
            }
        },
        "CreateClient",
    )

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.return_value.client.side_effect = error

        with pytest.raises(ClientInitializationError) as exc_info:
            AWSClients.get_s3_client()

    message = str(exc_info.value)
    assert FAKE_ACCESS_KEY not in message
    assert FAKE_SECRET_KEY not in message
    assert FAKE_SESSION_TOKEN not in message
    assert message.count("***") == EXPECTED_THREE
    assert "Failed to initialize S3 client" in message


def test_error_message_is_untouched_without_credentials(reset_clients: None) -> None:
    """Redaction leaves an ordinary error message alone."""
    error = ClientError(
        {"Error": {"Code": "UnrecognizedClientException", "Message": "bad token"}},
        "CreateClient",
    )

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.return_value.client.side_effect = error

        with pytest.raises(ClientInitializationError, match="bad token") as exc_info:
            AWSClients.get_textract_client()

    assert "***" not in str(exc_info.value)
