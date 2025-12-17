"""Bedrock operations module."""

import json
from typing import Any, cast

from botocore.exceptions import ClientError

from ._clients import AWSClients
from .config import config
from .exceptions import BedrockError


def invoke(
    prompt: str,
    model_id: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    system_prompt: str | None = None,
) -> str:
    """
    Invoke Bedrock LLM and return text response.

    Args:
        prompt: User prompt/question
        model_id: Model ID (uses AWS_BEDROCK_MODEL_ID env var if not specified)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 to 1.0)
        system_prompt: Optional system prompt

    Returns:
        Generated text response

    Raises:
        BedrockError: If invocation fails
    """
    model_id = model_id or config.bedrock_model_id

    try:
        client = AWSClients.get_bedrock_runtime_client()

        # Build request based on model family
        if "anthropic.claude" in model_id:
            body = _build_anthropic_request(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )
        else:
            raise BedrockError(
                f"Unsupported model family: {model_id}. Currently only Claude models are supported."
            )

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())

        # Extract text based on model family
        if "anthropic.claude" in model_id:
            return _extract_anthropic_text(response_body)
        else:
            raise BedrockError(f"Cannot extract response from model: {model_id}")

    except ClientError as e:
        raise BedrockError(f"Failed to invoke Bedrock model {model_id}: {e}") from e
    except Exception as e:
        raise BedrockError(f"Unexpected error invoking Bedrock: {e}") from e


def invoke_json(
    prompt: str,
    model_id: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """
    Invoke Bedrock LLM and return parsed JSON response.

    The prompt should explicitly ask for JSON output.

    Args:
        prompt: User prompt (should request JSON output)
        model_id: Model ID (uses AWS_BEDROCK_MODEL_ID env var if not specified)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 to 1.0)
        system_prompt: Optional system prompt

    Returns:
        Parsed JSON response as dictionary

    Raises:
        BedrockError: If invocation fails or response is not valid JSON
    """
    # Add JSON instruction if not present
    json_prompt = prompt
    if "json" not in prompt.lower():
        json_prompt = f"{prompt}\n\nPlease respond with valid JSON only."

    text_response = invoke(
        prompt=json_prompt,
        model_id=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
    )

    try:
        # Try to parse the response as JSON
        # Handle cases where model wraps JSON in markdown code blocks
        cleaned = text_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        return cast(dict[str, Any], json.loads(cleaned))
    except json.JSONDecodeError as e:
        raise BedrockError(
            f"Model response is not valid JSON. Response: {text_response[:200]}..."
        ) from e


def _build_anthropic_request(
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Build request body for Anthropic Claude models."""
    body: dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    if system_prompt:
        body["system"] = system_prompt

    return body


def _extract_anthropic_text(response_body: dict[str, Any]) -> str:
    """Extract text from Anthropic Claude response."""
    content = response_body.get("content", [])
    if not content:
        raise BedrockError("Empty response from model")

    # Claude returns content as list of content blocks
    text_parts = []
    for block in content:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return "".join(text_parts)
