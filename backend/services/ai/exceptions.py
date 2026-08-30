"""Safe, user-facing AI exception hierarchy."""

from __future__ import annotations

from typing import Any


class AIServiceError(Exception):
    """Base AI error with a safe category and frontend-safe message."""

    category = "ai_error"
    default_message = "AI roadmap generation is currently unavailable. Please try again."

    def __init__(self, message: str | None = None):
        self.user_message = message or self.default_message
        super().__init__(self.user_message)


class AIConfigurationError(AIServiceError):
    category = "configuration"
    default_message = (
        "AI roadmap generation is not configured. Ask an administrator to "
        "set up the OpenAI connection."
    )


class AIAuthenticationError(AIServiceError):
    category = "authentication"
    default_message = (
        "AI roadmap generation is currently unavailable due to an authentication issue."
    )


class AIQuotaError(AIServiceError):
    category = "quota"
    default_message = (
        "AI roadmap generation is temporarily unavailable due to account limits. "
        "Please try again later."
    )


class AIRateLimitError(AIServiceError):
    category = "rate_limit"
    default_message = (
        "AI roadmap generation is temporarily rate-limited. Please try again shortly."
    )


class AITimeoutError(AIServiceError):
    category = "timeout"
    default_message = (
        "AI roadmap generation timed out. Please try generating the roadmap again."
    )


class AIInvalidOutputError(AIServiceError):
    """
    Invalid AI structured/business output.

    ``user_message`` stays frontend-safe. ``diagnostic`` / detail fields are for
    server-side logging only and must never be returned to clients as-is.
    """

    category = "invalid_output"
    default_message = (
        "AI roadmap generation could not produce a valid roadmap. Please try again."
    )

    def __init__(
        self,
        message: str | None = None,
        *,
        diagnostic: str | None = None,
        reason: str | None = None,
        path: str | None = None,
        expected: Any = None,
        received: Any = None,
        program_id: Any = None,
        week_number: Any = None,
        task_number: Any = None,
        task_title: str | None = None,
        error_type: str | None = None,
        fragment: Any = None,
    ):
        self.reason = reason
        self.path = path
        self.expected = expected
        self.received = received
        self.program_id = program_id
        self.week_number = week_number
        self.task_number = task_number
        self.task_title = task_title
        self.error_type = error_type or self.__class__.__name__
        self.fragment = fragment
        self.diagnostic = diagnostic or self._build_diagnostic()
        # Always keep the API-facing message generic/safe.
        super().__init__(message or self.default_message)

    def _build_diagnostic(self) -> str:
        lines = [f"error_type={self.error_type}"]
        if self.reason:
            lines.append(f"reason={self.reason}")
        if self.program_id is not None:
            lines.append(f"program_id={self.program_id}")
        if self.path:
            lines.append(f"path={self.path}")
        if self.week_number is not None:
            lines.append(f"week_number={self.week_number}")
        if self.task_number is not None:
            lines.append(f"task_number={self.task_number}")
        if self.task_title:
            lines.append(f"task_title={self.task_title}")
        if self.expected is not None:
            lines.append(f"expected={self.expected}")
        if self.received is not None:
            lines.append(f"received={self.received}")
        return "; ".join(lines)


class AIPermissionError(AIServiceError):
    category = "permission"
    default_message = "You do not have permission to generate a roadmap for this program."


class AIValidationError(AIServiceError):
    category = "validation"
    default_message = "The selected program or intern scope is invalid."


class AIPersistenceError(AIServiceError):
    category = "persistence"
    default_message = (
        "AI roadmap generation succeeded but could not be saved. Please try again."
    )
