"""Orchestrate two-step AI final internship summary generation."""

from __future__ import annotations

from typing import Any

from apps.reports.models import FinalInternshipSummary
from common.constants import Role
from services.ai import config
from services.ai.exceptions import AIPermissionError, AIServiceError, AIValidationError
from services.ai.final_summary_context import (
    assemble_final_summary_context,
    resolve_final_summary_targets,
)
from services.ai.final_summary_final_prompt import (
    build_final_final_summary_generation_prompt,
)
from services.ai.final_summary_generator import generate_final_summary_structure
from services.ai.final_summary_persistence import persist_generated_final_summary
from services.ai.final_summary_prompt_builder import build_final_summary_prompt
from services.ai.logging_utils import generation_timer
from services.ai.preview_store import (
    FINAL_SUMMARY_PREVIEW_KEY_PREFIX,
    delete_preview,
    load_preview,
    store_preview,
)


def build_ai_final_summary_prompt_preview(
    *,
    mentor,
    program_id: int,
    intern_id: int,
) -> dict[str, Any]:
    """
    Step 1: Context → OpenAI Call #1 → Final Prompt. No Call #2. No DB summary write.
    """
    program, intern = resolve_final_summary_targets(
        mentor=mentor,
        program_id=program_id,
        intern_id=intern_id,
    )

    with generation_timer(
        feature_type="FINAL_SUMMARY_PROMPT",
        user_id=mentor.id,
        program_id=program.id,
        prompt_builder_model=config.prompt_builder_model(),
        generator_model=config.final_summary_model(),
    ):
        context = assemble_final_summary_context(program=program, intern=intern)
        prompt_builder_result = build_final_summary_prompt(context)
        final_prompt = build_final_final_summary_generation_prompt(
            context=context,
            prompt_builder_result=prompt_builder_result,
        )
        preview_id = store_preview(
            mentor_id=mentor.id,
            key_prefix=FINAL_SUMMARY_PREVIEW_KEY_PREFIX,
            payload={
                "program_id": program.id,
                "intern_id": intern.id,
                "canonical_context": context,
                "prompt_builder_result": prompt_builder_result.model_dump(),
                "final_final_summary_generation_prompt": final_prompt,
            },
        )
        return {
            "preview_id": preview_id,
            "prompt_title": prompt_builder_result.prompt_title,
            "final_final_summary_generation_prompt": final_prompt,
            "important_constraints": prompt_builder_result.important_constraints,
            "personalization_points": prompt_builder_result.personalization_points,
            "missing_context_notes": list(
                dict.fromkeys(
                    list(prompt_builder_result.missing_context_notes)
                    + list(context.get("unavailable_data") or [])
                )
            ),
            "program_id": program.id,
            "intern_id": intern.id,
        }


def continue_ai_final_summary_generation(
    *,
    mentor,
    preview_id: str,
) -> FinalInternshipSummary:
    """
    Step 2: Load exact previewed Final Prompt → OpenAI Call #2 → validate → persist DRAFT.
    """
    if getattr(mentor, "role", None) != Role.MENTOR:
        raise AIPermissionError()

    preview = load_preview(
        preview_id=preview_id,
        mentor_id=mentor.id,
        key_prefix=FINAL_SUMMARY_PREVIEW_KEY_PREFIX,
    )
    program, intern = resolve_final_summary_targets(
        mentor=mentor,
        program_id=preview["program_id"],
        intern_id=preview["intern_id"],
    )
    context = preview["canonical_context"]
    final_prompt = preview["final_final_summary_generation_prompt"]

    with generation_timer(
        feature_type="FINAL_SUMMARY",
        user_id=mentor.id,
        program_id=program.id,
        prompt_builder_model=config.prompt_builder_model(),
        generator_model=config.final_summary_model(),
    ):
        generated = generate_final_summary_structure(
            context=context,
            final_final_summary_generation_prompt=final_prompt,
        )
        summary = persist_generated_final_summary(
            program=program,
            intern=intern,
            generated=generated,
        )
        delete_preview(preview_id, key_prefix=FINAL_SUMMARY_PREVIEW_KEY_PREFIX)
        return summary


def to_final_summary_api_error_payload(exc: Exception) -> tuple[int, dict]:
    if isinstance(exc, AIPermissionError):
        return 403, {"detail": exc.user_message}
    if isinstance(exc, AIValidationError):
        return 400, {"detail": exc.user_message}
    if isinstance(exc, AIServiceError):
        return 503, {"detail": exc.user_message}
    return 503, {
        "detail": "AI final summary generation is currently unavailable. Please try again."
    }
