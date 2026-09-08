"""Bedrock operations module."""

import json
from collections.abc import Callable
from typing import Any, cast

from botocore.exceptions import ClientError

from ._clients import AWSClients
from .config import config
from .exceptions import BedrockError

BuildRequestFn = Callable[..., dict[str, Any]]
ExtractTextFn = Callable[[dict[str, Any]], str]


def invoke(
    prompt: str,
    model_id: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
    system_prompt: str | None = None,
) -> str:
    """
    Invoke Bedrock LLM and return text response.

    Supports Anthropic Claude, Amazon Titan, Meta Llama and Mistral model
    families, selected from the model_id. Other families raise BedrockError.

    Args:
        prompt: User prompt/question
        model_id: Model ID (uses AWS_BEDROCK_MODEL_ID env var if not specified),
            e.g. "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "amazon.titan-text-express-v1", "meta.llama3-8b-instruct-v1:0" or
            "mistral.mistral-7b-instruct-v0:2".
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 to 1.0)
        system_prompt: Optional system prompt

    Returns:
        Generated text response

    Raises:
        BedrockError: If invocation fails, or if model_id's family is not supported
    """
    model_id = model_id or config.bedrock_model_id
    build_request, extract_text = _resolve_family(model_id)

    try:
        client = AWSClients.get_bedrock_runtime_client()

        body = build_request(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
        )

        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())

        return extract_text(response_body)

    except ClientError as e:
        raise BedrockError(f"Failed to invoke Bedrock model {model_id}: {e}") from e
    except BedrockError:
        raise
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


def _with_system_prompt(prompt: str, system_prompt: str | None) -> str:
    """Prepend a system prompt for model families with no dedicated field for it."""
    return f"{system_prompt}\n\n{prompt}" if system_prompt else prompt


def _build_titan_request(
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Build request body for Amazon Titan text models."""
    return {
        "inputText": _with_system_prompt(prompt, system_prompt),
        "textGenerationConfig": {
            "maxTokenCount": max_tokens,
            "temperature": temperature,
        },
    }


def _extract_titan_text(response_body: dict[str, Any]) -> str:
    """Extract text from Amazon Titan response."""
    results = response_body.get("results", [])
    if not results:
        raise BedrockError("Empty response from model")

    return "".join(result.get("outputText", "") for result in results)


def _build_llama_request(
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Build request body for Meta Llama models."""
    return {
        "prompt": _with_system_prompt(prompt, system_prompt),
        "max_gen_len": max_tokens,
        "temperature": temperature,
    }


def _extract_llama_text(response_body: dict[str, Any]) -> str:
    """Extract text from Meta Llama response."""
    text = response_body.get("generation")
    if not text:
        raise BedrockError("Empty response from model")

    return cast(str, text)


def _build_mistral_request(
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Build request body for Mistral models."""
    return {
        "prompt": f"<s>[INST] {_with_system_prompt(prompt, system_prompt)} [/INST]",
        "max_tokens": max_tokens,
        "temperature": temperature,
    }


def _extract_mistral_text(response_body: dict[str, Any]) -> str:
    """Extract text from Mistral response."""
    outputs = response_body.get("outputs", [])
    if not outputs:
        raise BedrockError("Empty response from model")

    return "".join(output.get("text", "") for output in outputs)


# Model family handlers, keyed by the substring identifying the family in a model_id.
_MODEL_FAMILIES: dict[str, tuple[BuildRequestFn, ExtractTextFn]] = {
    "anthropic.claude": (_build_anthropic_request, _extract_anthropic_text),
    "amazon.titan": (_build_titan_request, _extract_titan_text),
    "meta.llama": (_build_llama_request, _extract_llama_text),
    "mistral.": (_build_mistral_request, _extract_mistral_text),
}


def _resolve_family(model_id: str) -> tuple[BuildRequestFn, ExtractTextFn]:
    """Look up the request builder and text extractor for a model_id's family."""
    for family, handlers in _MODEL_FAMILIES.items():
        if family in model_id:
            return handlers

    supported = ", ".join(_MODEL_FAMILIES)
    raise BedrockError(f"Unsupported model family: {model_id}. Supported families: {supported}.")
