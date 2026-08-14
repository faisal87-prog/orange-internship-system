"""Lightweight reusable AI generation logging (no secrets)."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("ai.generation")


@contextmanager
def generation_timer(
    *,
    feature_type: str,
    user_id: int | None,
    program_id: int | None,
    prompt_builder_model: str,
    generator_model: str,
) -> Iterator[dict]:
    """Yield a mutable event dict and log success/failure safely."""
    started = time.monotonic()
    event = {
        "feature_type": feature_type,
        "user_id": user_id,
        "program_id": program_id,
        "prompt_builder_model": prompt_builder_model,
        "generator_model": generator_model,
        "success": False,
        "error_category": None,
    }
    try:
        yield event
        event["success"] = True
    except Exception as exc:  # noqa: BLE001
        category = getattr(exc, "category", "unexpected")
        event["error_category"] = category
        raise
    finally:
        event["duration_ms"] = int((time.monotonic() - started) * 1000)
        logger.info(
            "ai_generation feature=%s success=%s category=%s duration_ms=%s "
            "user_id=%s program_id=%s prompt_model=%s generator_model=%s",
            event["feature_type"],
            event["success"],
            event.get("error_category") or "-",
            event.get("duration_ms"),
            event.get("user_id"),
            event.get("program_id"),
            event.get("prompt_builder_model"),
            event.get("generator_model"),
        )
