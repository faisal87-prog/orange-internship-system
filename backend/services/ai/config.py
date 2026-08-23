"""Centralized OpenAI configuration.

Never log or return the API key value.
"""

from django.conf import settings


def openai_api_key() -> str:
    return (getattr(settings, "OPENAI_API_KEY", None) or "").strip()


def prompt_builder_model() -> str:
    return getattr(settings, "OPENAI_PROMPT_BUILDER_MODEL", "gpt-5.6-terra")


def roadmap_model() -> str:
    return getattr(settings, "OPENAI_ROADMAP_MODEL", "gpt-5.6-terra")


def weekly_report_model() -> str:
    return getattr(
        settings,
        "OPENAI_WEEKLY_REPORT_MODEL",
        None,
    ) or roadmap_model()


def openai_timeout_seconds() -> float:
    return float(getattr(settings, "OPENAI_TIMEOUT_SECONDS", 60))


def require_api_key() -> str:
    key = openai_api_key()
    if not key:
        from services.ai.exceptions import AIConfigurationError

        raise AIConfigurationError(
            "AI roadmap generation is currently unavailable. Please try again."
        )
    return key
