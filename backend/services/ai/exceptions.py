"""Safe, user-facing AI exception hierarchy."""


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
    category = "invalid_output"
    default_message = (
        "AI roadmap generation could not produce a valid roadmap. Please try again."
    )


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
