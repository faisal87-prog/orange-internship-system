"""Short-lived server-side store for AI roadmap prompt previews."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.core.cache import cache

from services.ai.exceptions import AIPermissionError, AIValidationError

PREVIEW_KEY_PREFIX = "ai_roadmap_preview:"


def _ttl() -> int:
    return int(getattr(settings, "AI_ROADMAP_PREVIEW_TTL_SECONDS", 1200))


def _key(preview_id: str) -> str:
    return f"{PREVIEW_KEY_PREFIX}{preview_id}"


def store_preview(*, mentor_id: int, payload: dict[str, Any]) -> str:
    preview_id = str(uuid.uuid4())
    data = {
        **payload,
        "mentor_id": mentor_id,
        "preview_id": preview_id,
    }
    cache.set(_key(preview_id), data, timeout=_ttl())
    return preview_id


def load_preview(*, preview_id: str, mentor_id: int) -> dict[str, Any]:
    if not preview_id:
        raise AIValidationError("A valid prompt preview is required.")
    data = cache.get(_key(preview_id))
    if not data:
        raise AIValidationError(
            "This AI prompt preview has expired. Please build the prompt again."
        )
    if int(data.get("mentor_id") or 0) != int(mentor_id):
        raise AIPermissionError(
            "You do not have permission to use this AI prompt preview."
        )
    return data


def delete_preview(preview_id: str) -> None:
    cache.delete(_key(preview_id))
