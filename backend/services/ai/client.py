"""OpenAI Responses API client wrapper (server-side only)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from services.ai import config
from services.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIQuotaError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)

T = TypeVar("T", bound=BaseModel)


def _map_openai_error(exc: Exception) -> AIServiceError:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()

    if "timeout" in name or "timeout" in message:
        return AITimeoutError()
    if "authentication" in name or "unauthorized" in message or "invalid api key" in message:
        return AIAuthenticationError()
    if "rate" in name or "rate limit" in message:
        return AIRateLimitError()
    if "quota" in message or "insufficient" in message or "billing" in message:
        return AIQuotaError()
    if "api_key" in message and ("missing" in message or "required" in message):
        return AIConfigurationError()
    return AIServiceError()


def get_openai_client():
    """Build the official OpenAI client. Key is never logged."""
    from openai import OpenAI

    api_key = config.require_api_key()
    return OpenAI(api_key=api_key, timeout=config.openai_timeout_seconds())


def parse_structured(
    *,
    model: str,
    input_messages: list[dict],
    text_format: type[T],
) -> T:
    """
    Call the OpenAI Responses API with Structured Outputs.

    Returns a validated Pydantic instance. Never returns secrets.
    """
    try:
        client = get_openai_client()
        response = client.responses.parse(
            model=model,
            input=input_messages,
            text_format=text_format,
        )
    except AIServiceError:
        raise
    except Exception as exc:  # noqa: BLE001 - map vendor errors safely
        raise _map_openai_error(exc) from exc

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        refusal = None
        try:
            refusal = getattr(response, "output_text", None)
        except Exception:  # noqa: BLE001
            refusal = None
        from services.ai.exceptions import AIInvalidOutputError

        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
            if not refusal
            else "AI roadmap generation could not produce a valid roadmap. Please try again."
        )
    return parsed
