"""Tests for the programmatic configure() API and cache invalidation."""

import inspect
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

import aws_simple
from aws_simple import configure, reset_configuration, s3
from aws_simple._clients import AWSClients
from aws_simple.config import SETTING_ENV_VARS, Config, config
from aws_simple.exceptions import ClientInitializationError, ConfigurationError

pytestmark = pytest.mark.unit

# One redaction per credential quoted in the error message below.
EXPECTED_REDACTIONS = 3

# Fake credential material — never real keys, only used to assert plumbing
# and that nothing leaks into repr or error messages.
FAKE_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
FAKE_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
FAKE_SESSION_TOKEN = "FQoGZXIvYXdzEXAMPLESESSIONTOKEN"


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def test_configure_is_exported_from_the_package() -> None:
    """configure() and reset_configuration() are part of the public API."""
    assert aws_simple.configure is configure
    assert aws_simple.reset_configuration is reset_configuration
    assert "configure" in aws_simple.__all__
    assert "reset_configuration" in aws_simple.__all__


def test_configure_signature_matches_the_settings_registry() -> None:
    """Every configure() keyword is a registered setting, and vice versa."""
    parameters = inspect.signature(configure).parameters

    assert set(parameters) == set(SETTING_ENV_VARS)
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in parameters.values())
    assert all(p.default is None for p in parameters.values())


# ---------------------------------------------------------------------------
# cache invalidation — the trap from issue #31
# ---------------------------------------------------------------------------


def test_configure_after_a_client_was_built_applies_to_the_next_call(
    reset_clients: None,
) -> None:
    """Regression test for the silent trap described in issue #31.

    The equivalent os.environ mutation used to be ignored because the cached
    client was never invalidated; going through configure() must not be.
    """
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        mock_session.return_value.client.return_value.list_objects_v2.return_value = {}

        s3.list_objects("a/")  # client built for the env-var region
        assert mock_session.call_args.kwargs["region_name"] == "us-east-1"

        configure(region="eu-west-3")

        s3.list_objects("b/")  # must be a *new* client, in the new region
        assert mock_session.call_args.kwargs["region_name"] == "eu-west-3"


def test_configure_rebuilds_every_cached_client(reset_clients: None) -> None:
    """S3, Textract and Bedrock clients are all invalidated."""
    with patch("aws_simple._clients.boto3.Session") as mock_session:
        first = (
            AWSClients.get_s3_client(),
            AWSClients.get_textract_client(),
            AWSClients.get_bedrock_runtime_client(),
        )

        configure(region="eu-west-3")
        mock_session.return_value.client.return_value = MagicMock()

        assert AWSClients.get_s3_client() is not first[0]
        assert AWSClients.get_textract_client() is not first[1]
        assert AWSClients.get_bedrock_runtime_client() is not first[2]


def test_reset_configuration_invalidates_the_cache(reset_clients: None) -> None:
    """Dropping the overrides is a mutation too, so the cache is invalidated."""
    configure(region="eu-west-3")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()
        assert mock_session.call_args.kwargs["region_name"] == "eu-west-3"

        reset_configuration()

        AWSClients.get_s3_client()
        assert mock_session.call_args.kwargs["region_name"] == "us-east-1"


# ---------------------------------------------------------------------------
# precedence
# ---------------------------------------------------------------------------


def test_configure_overrides_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """configure() wins over an environment variable."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_S3_BUCKET", "env-bucket")

    configure(region="eu-west-3", bucket="configured-bucket")

    assert config.aws_region == "eu-west-3"
    assert config.s3_bucket == "configured-bucket"


def test_environment_variables_apply_to_settings_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings not passed to configure() keep coming from the environment."""
    monkeypatch.setenv("AWS_S3_BUCKET", "env-bucket")

    configure(region="eu-west-3")

    assert config.s3_bucket == "env-bucket"


def test_configure_calls_accumulate() -> None:
    """Successive calls add up; omitted arguments are left untouched."""
    configure(region="eu-west-3")
    configure(bucket="my-bucket")

    assert config.aws_region == "eu-west-3"
    assert config.s3_bucket == "my-bucket"


def test_reset_configuration_falls_back_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a reset the environment is authoritative again."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    configure(region="eu-west-3")

    reset_configuration()

    assert config.aws_region == "us-east-1"


def test_configured_required_value_satisfies_a_missing_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A required setting can be supplied entirely from code."""
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)

    configure(bucket="configured-bucket")

    assert config.s3_bucket == "configured-bucket"


def test_missing_required_value_mentions_configure(monkeypatch: pytest.MonkeyPatch) -> None:
    """The error for a missing required setting points at configure() too."""
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)

    with pytest.raises(ConfigurationError, match="configure"):
        _ = Config().s3_bucket


def test_overrides_are_per_instance() -> None:
    """Overriding the singleton never leaks into another Config instance."""
    configure(region="eu-west-3")

    assert Config().aws_region == "us-east-1"


# ---------------------------------------------------------------------------
# covered settings
# ---------------------------------------------------------------------------


def test_configure_sets_endpoints_for_every_service() -> None:
    """A global endpoint passed to configure() reaches every service."""
    configure(endpoint_url="http://localhost:4566")

    assert config.endpoint_url == "http://localhost:4566"
    assert config.s3_endpoint_url == "http://localhost:4566"
    assert config.textract_endpoint_url == "http://localhost:4566"
    assert config.bedrock_endpoint_url == "http://localhost:4566"


def test_configure_per_service_endpoints_override_the_global_one() -> None:
    """Per-service endpoints keep winning when set through configure()."""
    configure(
        endpoint_url="http://localhost:4566",
        s3_endpoint_url="http://localhost:9000",
        textract_endpoint_url="http://localhost:9001",
        bedrock_endpoint_url="http://localhost:9002",
    )

    assert config.s3_endpoint_url == "http://localhost:9000"
    assert config.textract_endpoint_url == "http://localhost:9001"
    assert config.bedrock_endpoint_url == "http://localhost:9002"


def test_configure_sets_profile_regions_and_model() -> None:
    """The remaining settings are wired to their config properties."""
    configure(
        profile="dev-profile",
        textract_region="us-west-2",
        bedrock_region="ap-southeast-1",
        bedrock_model_id="custom-model-id",
    )

    assert config.aws_profile == "dev-profile"
    assert config.textract_region == "us-west-2"
    assert config.bedrock_region == "ap-southeast-1"
    assert config.bedrock_model_id == "custom-model-id"


def test_configured_endpoint_reaches_the_client(reset_clients: None) -> None:
    """An endpoint set from code ends up in the boto3 client call."""
    configure(endpoint_url="http://localhost:4566")

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    assert mock_session.return_value.client.call_args.kwargs["endpoint_url"] == (
        "http://localhost:4566"
    )


# ---------------------------------------------------------------------------
# credentials
# ---------------------------------------------------------------------------


def test_configured_credentials_reach_the_session(reset_clients: None) -> None:
    """A complete credential set passed to configure() is forwarded to boto3."""
    configure(
        aws_access_key_id=FAKE_ACCESS_KEY,
        aws_secret_access_key=FAKE_SECRET_KEY,
        aws_session_token=FAKE_SESSION_TOKEN,
    )

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    kwargs = mock_session.call_args.kwargs
    assert kwargs["aws_access_key_id"] == FAKE_ACCESS_KEY
    assert kwargs["aws_secret_access_key"] == FAKE_SECRET_KEY
    assert kwargs["aws_session_token"] == FAKE_SESSION_TOKEN


def test_partial_configured_credentials_are_ignored(reset_clients: None) -> None:
    """Half a credential pair must not break the default credential chain."""
    configure(aws_access_key_id=FAKE_ACCESS_KEY)

    assert config.has_explicit_credentials is False

    with patch("aws_simple._clients.boto3.Session") as mock_session:
        AWSClients.get_s3_client()

    assert "aws_access_key_id" not in mock_session.call_args.kwargs


def test_configured_credentials_never_appear_in_the_repr() -> None:
    """Credentials set from code stay out of the Config repr."""
    configure(aws_access_key_id=FAKE_ACCESS_KEY, aws_secret_access_key=FAKE_SECRET_KEY)

    text = repr(config)

    assert text == "Config()"
    assert FAKE_ACCESS_KEY not in text
    assert FAKE_SECRET_KEY not in text


def test_configured_credentials_are_scrubbed_from_client_errors(reset_clients: None) -> None:
    """A botocore error quoting credentials set from code is redacted."""
    configure(
        aws_access_key_id=FAKE_ACCESS_KEY,
        aws_secret_access_key=FAKE_SECRET_KEY,
        aws_session_token=FAKE_SESSION_TOKEN,
    )
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

        with pytest.raises(ClientInitializationError) as excinfo:
            AWSClients.get_s3_client()

    message = str(excinfo.value)
    assert FAKE_ACCESS_KEY not in message
    assert FAKE_SECRET_KEY not in message
    assert FAKE_SESSION_TOKEN not in message
    assert message.count("***") == EXPECTED_REDACTIONS


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def test_unknown_setting_is_rejected() -> None:
    """set_overrides() names the unsupported setting and the supported ones."""
    with pytest.raises(ConfigurationError, match="Unknown configuration setting"):
        config.set_overrides({"nope": "value"})


def test_non_string_value_is_rejected_without_echoing_it() -> None:
    """A wrong type is reported by name only — the value may be a secret."""
    with pytest.raises(ConfigurationError) as excinfo:
        config.set_overrides({"aws_secret_access_key": FAKE_SECRET_KEY.encode()})  # type: ignore[dict-item]

    assert "aws_secret_access_key" in str(excinfo.value)
    assert FAKE_SECRET_KEY not in str(excinfo.value)


def test_a_rejected_call_changes_nothing() -> None:
    """Validation happens before any override is applied."""
    config.set_overrides({"region": "eu-west-3"})

    with pytest.raises(ConfigurationError):
        config.set_overrides({"bucket": "late-bucket", "nope": "value"})

    assert config.aws_region == "eu-west-3"
    assert config.s3_bucket == "test-bucket"
