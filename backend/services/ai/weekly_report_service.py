"""Orchestrate two-step AI weekly report generation."""

from __future__ import annotations

from typing import Any

from apps.reports.models import WeeklyReport
from common.constants import Role
from services.ai import config
from services.ai.exceptions import AIPermissionError, AIServiceError, AIValidationError
from services.ai.logging_utils import generation_timer
from services.ai.preview_store import (
    WEEKLY_REPORT_PREVIEW_KEY_PREFIX,
    delete_preview,
    load_preview,
    store_preview,
)
from services.ai.weekly_report_context import (
    assemble_weekly_report_context,
    resolve_weekly_report_targets,
)
from services.ai.weekly_report_final_prompt import (
    build_final_weekly_report_generation_prompt,
)
from services.ai.weekly_report_generator import generate_weekly_report_structure
from services.ai.weekly_report_persistence import persist_generated_weekly_report
from services.ai.weekly_report_prompt_builder import build_weekly_report_prompt


def build_ai_weekly_report_prompt_preview(
    *,
    mentor,
    program_id: int,
    intern_id: int,
    roadmap_week_id: int,
) -> dict[str, Any]:
    """
    Step 1: Context → OpenAI Call #1 → Final Prompt. No Call #2. No DB report write.
    """
    program, intern, week, roadmap = resolve_weekly_report_targets(
        mentor=mentor,
        program_id=program_id,
        intern_id=intern_id,
        roadmap_week_id=roadmap_week_id,
    )

    with generation_timer(
        feature_type="WEEKLY_REPORT_PROMPT",
        user_id=mentor.id,
        program_id=program.id,
        prompt_builder_model=config.prompt_builder_model(),
        generator_model=config.weekly_report_model(),
    ):
        context = assemble_weekly_report_context(
            program=program,
            intern=intern,
            week=week,
            roadmap=roadmap,
        )
        prompt_builder_result = build_weekly_report_prompt(context)
        final_prompt = build_final_weekly_report_generation_prompt(
            context=context,
            prompt_builder_result=prompt_builder_result,
        )
        preview_id = store_preview(
            mentor_id=mentor.id,
            key_prefix=WEEKLY_REPORT_PREVIEW_KEY_PREFIX,
            payload={
                "program_id": program.id,
                "intern_id": intern.id,
                "roadmap_week_id": week.id,
                "canonical_context": context,
                "prompt_builder_result": prompt_builder_result.model_dump(),
                "final_weekly_report_generation_prompt": final_prompt,
            },
        )
        return {
            "preview_id": preview_id,
            "prompt_title": prompt_builder_result.prompt_title,
            "final_weekly_report_generation_prompt": final_prompt,
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
            "roadmap_week_id": week.id,
            "week_number": week.week_number,
            "overall_weekly_score": (context.get("weekly_score") or {}).get(
                "overall_weekly_score"
            ),
        }


def continue_ai_weekly_report_generation(
    *,
    mentor,
    preview_id: str,
) -> WeeklyReport:
    """
    Step 2: Load exact previewed Final Prompt → OpenAI Call #2 → validate → persist DRAFT.
    """
    if getattr(mentor, "role", None) != Role.MENTOR:
        raise AIPermissionError()

    preview = load_preview(
        preview_id=preview_id,
        mentor_id=mentor.id,
        key_prefix=WEEKLY_REPORT_PREVIEW_KEY_PREFIX,
    )
    program, intern, week, roadmap = resolve_weekly_report_targets(
        mentor=mentor,
        program_id=preview["program_id"],
        intern_id=preview["intern_id"],
        roadmap_week_id=preview["roadmap_week_id"],
    )
    context = preview["canonical_context"]
    final_prompt = preview["final_weekly_report_generation_prompt"]

    with generation_timer(
        feature_type="WEEKLY_REPORT",
        user_id=mentor.id,
        program_id=program.id,
        prompt_builder_model=config.prompt_builder_model(),
        generator_model=config.weekly_report_model(),
    ):
        generated = generate_weekly_report_structure(
            context=context,
            final_weekly_report_generation_prompt=final_prompt,
        )
        report = persist_generated_weekly_report(
            program=program,
            intern=intern,
            week=week,
            generated=generated,
        )
        delete_preview(preview_id, key_prefix=WEEKLY_REPORT_PREVIEW_KEY_PREFIX)
        return report


def to_weekly_report_api_error_payload(exc: Exception) -> tuple[int, dict]:
    if isinstance(exc, AIPermissionError):
        return 403, {"detail": exc.user_message}
    if isinstance(exc, AIValidationError):
        return 400, {"detail": exc.user_message}
    if isinstance(exc, AIServiceError):
        return 503, {"detail": exc.user_message}
    return 503, {
        "detail": "AI weekly report generation is currently unavailable. Please try again."
    }
