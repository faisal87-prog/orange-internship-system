"""OpenAI Responses API client wrapper (server-side only)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from services.ai import config
from services.ai.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIInvalidOutputError,
    AIQuotaError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from services.ai.logging_utils import log_roadmap_failure

T = TypeVar("T", bound=BaseModel)


def _map_openai_error(exc: Exception) -> AIServiceError:
    name = exc.__class__.__name__.lower()
    message = str(exc).lower()

    if isinstance(exc, ValidationError):
        return _invalid_from_validation_error(exc)

    # OpenAI SDK / Responses parse failures that wrap schema issues.
    if "validation" in name or "validation error" in message or "pydantic" in name:
        return AIInvalidOutputError(
            reason="OpenAI structured-output/schema validation failed",
            error_type=type(exc).__name__,
            received=str(exc)[:800],
        )

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


def _structured_failure_header(text_format: type | None) -> str:
    name = getattr(text_format, "__name__", "") or ""
    if "Roadmap" in name:
        return "ROADMAP_STRUCTURED_OUTPUT_FAILED"
    if "WeeklyReport" in name:
        return "WEEKLY_REPORT_STRUCTURED_OUTPUT_FAILED"
    if "FinalSummary" in name:
        return "FINAL_SUMMARY_STRUCTURED_OUTPUT_FAILED"
    return "STRUCTURED_OUTPUT_FAILED"


def _invalid_from_validation_error(
    exc: ValidationError,
    *,
    text_format: type | None = None,
) -> AIInvalidOutputError:
    first = exc.errors()[0] if exc.errors() else {}
    loc = first.get("loc") or ()
    path = ".".join(str(part) for part in loc) if loc else None
    expected = first.get("type")
    if first.get("ctx"):
        expected = f"{expected}; ctx={first.get('ctx')}"
    received = first.get("input", first.get("msg"))
    reason = first.get("msg") or "Pydantic validation failed for structured output"
    header = _structured_failure_header(text_format)
    err = AIInvalidOutputError(
        reason=reason,
        path=path,
        expected=expected,
        received=received,
        error_type="PydanticValidationError",
        fragment=first,
        diagnostic=(
            f"{header}; path={path}; reason={reason}; "
            f"expected={expected}; received={received}"
        ),
    )
    log_roadmap_failure(
        header,
        exc=err,
        path=path,
        reason=reason,
        expected=expected,
        received=received,
        fragment=first,
    )
    return err


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
    except ValidationError as exc:
        raise _invalid_from_validation_error(exc, text_format=text_format) from exc
    except Exception as exc:  # noqa: BLE001 - map vendor errors safely
        mapped = _map_openai_error(exc)
        if isinstance(mapped, AIInvalidOutputError):
            log_roadmap_failure(
                _structured_failure_header(text_format),
                exc=mapped,
            )
        raise mapped from exc

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        refusal = None
        try:
            refusal = getattr(response, "output_text", None)
        except Exception:  # noqa: BLE001
            refusal = None
        header = _structured_failure_header(text_format)
        err = AIInvalidOutputError(
            reason="OpenAI returned no structured output_parsed payload",
            error_type="MissingStructuredOutput",
            expected=getattr(text_format, "__name__", str(text_format)),
            received=(str(refusal)[:400] if refusal else None),
            fragment={"refusal_or_output_text": (str(refusal)[:400] if refusal else None)},
            diagnostic=header,
        )
        log_roadmap_failure(header, exc=err)
        raise err
    return parsed
