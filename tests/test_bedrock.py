"""Tests for Bedrock module."""

import json
from io import BytesIO
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from aws_simple import bedrock
from aws_simple.exceptions import BedrockError


def test_invoke_success(mock_bedrock_client: MagicMock) -> None:
    """Test successful Bedrock invocation."""
    response_body = {
        "content": [{"type": "text", "text": "AWS Lambda is a serverless compute service."}]
    }

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    result = bedrock.invoke("Explain AWS Lambda")

    assert result == "AWS Lambda is a serverless compute service."
    mock_bedrock_client.invoke_model.assert_called_once()

    call_args = mock_bedrock_client.invoke_model.call_args
    assert call_args.kwargs["modelId"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert call_args.kwargs["contentType"] == "application/json"

    # Verify request body
    body_str = call_args.kwargs["body"]
    body = json.loads(body_str)
    assert body["messages"][0]["content"] == "Explain AWS Lambda"
    assert "max_tokens" in body
    assert "temperature" in body


def test_invoke_with_system_prompt(mock_bedrock_client: MagicMock) -> None:
    """Test invocation with system prompt."""
    response_body = {"content": [{"type": "text", "text": "Response text"}]}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    bedrock.invoke(
        "What are the benefits?",
        system_prompt="You are an AWS solutions architect.",
        temperature=0.5,
        max_tokens=500,
    )

    call_args = mock_bedrock_client.invoke_model.call_args
    body = json.loads(call_args.kwargs["body"])

    assert body["system"] == "You are an AWS solutions architect."
    assert body["temperature"] == 0.5
    assert body["max_tokens"] == 500


def test_invoke_custom_model(mock_bedrock_client: MagicMock) -> None:
    """Test invocation with custom model."""
    response_body = {"content": [{"type": "text", "text": "Response"}]}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    bedrock.invoke("Test prompt", model_id="anthropic.claude-v2")

    call_args = mock_bedrock_client.invoke_model.call_args
    assert call_args.kwargs["modelId"] == "anthropic.claude-v2"


def test_invoke_multiple_content_blocks(mock_bedrock_client: MagicMock) -> None:
    """Test invocation with multiple content blocks in response."""
    response_body = {
        "content": [
            {"type": "text", "text": "First part. "},
            {"type": "text", "text": "Second part."},
        ]
    }

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    result = bedrock.invoke("Test")

    assert result == "First part. Second part."


def test_invoke_empty_response(mock_bedrock_client: MagicMock) -> None:
    """Test invocation with empty response."""
    response_body = {"content": []}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    with pytest.raises(BedrockError, match="Empty response from model"):
        bedrock.invoke("Test")


def test_invoke_client_error(mock_bedrock_client: MagicMock) -> None:
    """Test invocation with client error."""
    mock_bedrock_client.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "Invalid request"}}, "invoke_model"
    )

    with pytest.raises(BedrockError, match="Failed to invoke Bedrock"):
        bedrock.invoke("Test prompt")


def test_invoke_unsupported_model(mock_bedrock_client: MagicMock) -> None:
    """Test invocation with unsupported model family."""
    with pytest.raises(BedrockError, match="Unsupported model family"):
        bedrock.invoke("Test", model_id="amazon.titan-text-v1")


def test_invoke_json_success(mock_bedrock_client: MagicMock) -> None:
    """Test successful JSON invocation."""
    response_body = {
        "content": [
            {
                "type": "text",
                "text": '{"services": [{"name": "S3", "use_case": "Object storage"}]}',
            }
        ]
    }

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    result = bedrock.invoke_json("List AWS services")

    assert isinstance(result, dict)
    assert "services" in result
    assert result["services"][0]["name"] == "S3"


def test_invoke_json_with_markdown(mock_bedrock_client: MagicMock) -> None:
    """Test JSON invocation with markdown code block."""
    response_body = {
        "content": [
            {
                "type": "text",
                "text": '```json\n{"key": "value"}\n```',
            }
        ]
    }

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    result = bedrock.invoke_json("Return JSON")

    assert isinstance(result, dict)
    assert result["key"] == "value"


def test_invoke_json_adds_instruction(mock_bedrock_client: MagicMock) -> None:
    """Test that invoke_json adds JSON instruction to prompt."""
    response_body = {"content": [{"type": "text", "text": '{"data": "test"}'}]}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    bedrock.invoke_json("Extract data")

    call_args = mock_bedrock_client.invoke_model.call_args
    body = json.loads(call_args.kwargs["body"])
    prompt = body["messages"][0]["content"]

    assert "json" in prompt.lower()
    assert "Extract data" in prompt


def test_invoke_json_already_has_instruction(mock_bedrock_client: MagicMock) -> None:
    """Test that invoke_json doesn't duplicate JSON instruction."""
    response_body = {"content": [{"type": "text", "text": '{"result": "ok"}'}]}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    original_prompt = "Return data as JSON format"
    bedrock.invoke_json(original_prompt)

    call_args = mock_bedrock_client.invoke_model.call_args
    body = json.loads(call_args.kwargs["body"])
    prompt = body["messages"][0]["content"]

    # Should not add redundant instruction since "json" is already in prompt
    assert prompt == original_prompt


def test_invoke_json_invalid_response(mock_bedrock_client: MagicMock) -> None:
    """Test invoke_json with invalid JSON response."""
    response_body = {"content": [{"type": "text", "text": "This is not JSON"}]}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    with pytest.raises(BedrockError, match="Model response is not valid JSON"):
        bedrock.invoke_json("Return JSON")


def test_build_anthropic_request_structure(mock_bedrock_client: MagicMock) -> None:
    """Test the structure of Anthropic request body."""
    response_body = {"content": [{"type": "text", "text": "Response"}]}

    mock_bedrock_client.invoke_model.return_value = {
        "body": BytesIO(json.dumps(response_body).encode())
    }

    bedrock.invoke("Test", max_tokens=1000, temperature=0.8)

    call_args = mock_bedrock_client.invoke_model.call_args
    body = json.loads(call_args.kwargs["body"])

    assert body["anthropic_version"] == "bedrock-2023-05-31"
    assert body["max_tokens"] == 1000
    assert body["temperature"] == 0.8
    assert len(body["messages"]) == 1
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][0]["content"] == "Test"
