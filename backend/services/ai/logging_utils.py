"""Lightweight reusable AI generation logging (no secrets)."""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger("ai.generation")

_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|authorization|bearer|jwt|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
)


def _redact_secrets(text: str) -> str:
    cleaned = text or ""
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def _fmt_value(value: Any, *, max_len: int = 500) -> str:
    if value is None:
        return "-"
    text = str(value)
    text = _redact_secrets(text)
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def format_roadmap_debug_block(
    header: str,
    *,
    program_id: Any = None,
    reason: str | None = None,
    path: str | None = None,
    expected: Any = None,
    received: Any = None,
    week_number: Any = None,
    task_number: Any = None,
    task_title: str | None = None,
    error_type: str | None = None,
    fragment: Any = None,
    extra_lines: list[str] | None = None,
) -> str:
    """Multi-line development log block for roadmap generation failures."""
    lines = [header]
    if program_id is not None:
        lines.append(f"Program ID: {program_id}")
    if error_type:
        lines.append(f"Error type: {_fmt_value(error_type)}")
    if reason:
        lines.append(f"Reason: {_fmt_value(reason)}")
    if path:
        lines.append(f"Path: {_fmt_value(path)}")
    if week_number is not None:
        lines.append(f"Week number: {week_number}")
    if task_number is not None:
        lines.append(f"Task number: {task_number}")
    if task_title:
        lines.append(f"Task title: {_fmt_value(task_title)}")
    if expected is not None:
        lines.append(f"Expected: {_fmt_value(expected)}")
    if received is not None:
        lines.append(f"Received: {_fmt_value(received)}")
    if fragment is not None:
        lines.append(f"Invalid fragment: {_fmt_value(fragment, max_len=800)}")
    if extra_lines:
        lines.extend(extra_lines)
    return "\n".join(lines)


def log_roadmap_failure(header: str, *, exc: Exception | None = None, **fields: Any) -> None:
    """Log a ROADMAP_* failure block to the Django/development terminal."""
    if exc is not None:
        fields.setdefault("error_type", type(exc).__name__)
        fields.setdefault("reason", getattr(exc, "reason", None) or str(exc))
        fields.setdefault("path", getattr(exc, "path", None))
        fields.setdefault("expected", getattr(exc, "expected", None))
        fields.setdefault("received", getattr(exc, "received", None))
        fields.setdefault("program_id", getattr(exc, "program_id", None))
        fields.setdefault("week_number", getattr(exc, "week_number", None))
        fields.setdefault("task_number", getattr(exc, "task_number", None))
        fields.setdefault("task_title", getattr(exc, "task_title", None))
        fields.setdefault("fragment", getattr(exc, "fragment", None))
        diagnostic = getattr(exc, "diagnostic", None)
        if diagnostic and "extra_lines" not in fields:
            fields["extra_lines"] = [f"Diagnostic: {_fmt_value(diagnostic, max_len=1000)}"]
    block = format_roadmap_debug_block(header, **fields)
    logger.warning(_redact_secrets(block))


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
        diagnostic = getattr(exc, "diagnostic", None) or str(exc)
        logger.warning(
            "ai_generation_underlying_error feature=%s category=%s error_type=%s "
            "diagnostic=%s",
            feature_type,
            category,
            type(exc).__name__,
            _fmt_value(diagnostic, max_len=1000),
        )
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
