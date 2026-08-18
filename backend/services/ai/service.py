"""Orchestrate two-step AI roadmap generation (Prompt Builder then Generator)."""

from __future__ import annotations

from typing import Any

from apps.programs.models import InternshipProgram
from apps.roadmaps.models import Roadmap
from common.constants import Role
from services.ai import config
from services.ai.context_assembler import assemble_roadmap_context, resolve_scope_interns
from services.ai.exceptions import AIPermissionError, AIServiceError, AIValidationError
from services.ai.final_prompt import build_final_roadmap_generation_prompt
from services.ai.generators import generate_roadmap_structure
from services.ai.logging_utils import generation_timer
from services.ai.persistence import persist_generated_roadmap
from services.ai.preview_store import delete_preview, load_preview, store_preview
from services.ai.prompt_builder import build_roadmap_prompt
from services.ai.schemas import GeneratedRoadmapPrompt


def _load_owned_program(*, mentor, program_id: int) -> InternshipProgram:
    if getattr(mentor, "role", None) != Role.MENTOR:
        raise AIPermissionError()
    try:
        program = InternshipProgram.objects.select_related("mentor").prefetch_related(
            "reference_materials",
            "interns__skills",
            "interns__user",
        ).get(pk=program_id)
    except InternshipProgram.DoesNotExist as exc:
        raise AIValidationError("Program not found.") from exc
    if program.mentor_id != mentor.id:
        raise AIPermissionError()
    return program


def build_ai_roadmap_prompt_preview(
    *,
    mentor,
    program_id: int,
    assignment_scope: str,
    selected_intern_ids: list[int] | None = None,
    mentor_focus_skills: list[str] | None = None,
) -> dict[str, Any]:
    """
    Step 1: Context → OpenAI Call #1 → Final Prompt. No Call #2. No DB roadmap.
    """
    program = _load_owned_program(mentor=mentor, program_id=program_id)

    with generation_timer(
        feature_type="ROADMAP_PROMPT",
        user_id=mentor.id,
        program_id=program.id,
        prompt_builder_model=config.prompt_builder_model(),
        generator_model=config.roadmap_model(),
    ):
        interns = resolve_scope_interns(
            program=program,
            assignment_scope=assignment_scope,
            selected_intern_ids=selected_intern_ids,
            mentor_id=mentor.id,
        )
        context = assemble_roadmap_context(
            program=program,
            assignment_scope=assignment_scope,
            interns=interns,
            mentor_focus_skills=mentor_focus_skills,
        )
        prompt_builder_result = build_roadmap_prompt(context)
        final_prompt = build_final_roadmap_generation_prompt(
            context=context,
            prompt_builder_result=prompt_builder_result,
        )
        preview_id = store_preview(
            mentor_id=mentor.id,
            payload={
                "program_id": program.id,
                "assignment_scope": assignment_scope,
                "selected_intern_ids": [intern.id for intern in interns],
                "mentor_focus_skills": context.get("mentor_focus_skills") or [],
                "canonical_context": context,
                "prompt_builder_result": prompt_builder_result.model_dump(),
                "final_roadmap_generation_prompt": final_prompt,
            },
        )
        return {
            "preview_id": preview_id,
            "prompt_title": prompt_builder_result.prompt_title,
            "final_roadmap_generation_prompt": final_prompt,
            "important_constraints": prompt_builder_result.important_constraints,
            "personalization_points": prompt_builder_result.personalization_points,
            "missing_context_notes": list(
                dict.fromkeys(
                    list(prompt_builder_result.missing_context_notes)
                    + list(context.get("unavailable_data") or [])
                )
            ),
            "roadmap_scope": assignment_scope,
            "mentor_focus_skills": context.get("mentor_focus_skills") or [],
        }


def continue_ai_roadmap_generation(
    *,
    mentor,
    preview_id: str,
) -> Roadmap:
    """
    Step 2: Load exact previewed Final Prompt → OpenAI Call #2 → validate → persist DRAFT.
    """
    if getattr(mentor, "role", None) != Role.MENTOR:
        raise AIPermissionError()

    preview = load_preview(preview_id=preview_id, mentor_id=mentor.id)
    program = _load_owned_program(mentor=mentor, program_id=preview["program_id"])
    context = preview["canonical_context"]
    final_prompt = preview["final_roadmap_generation_prompt"]
    assignment_scope = preview["assignment_scope"]
    selected_ids = preview.get("selected_intern_ids") or []

    with generation_timer(
        feature_type="ROADMAP",
        user_id=mentor.id,
        program_id=program.id,
        prompt_builder_model=config.prompt_builder_model(),
        generator_model=config.roadmap_model(),
    ):
        interns = resolve_scope_interns(
            program=program,
            assignment_scope=assignment_scope,
            selected_intern_ids=selected_ids,
            mentor_id=mentor.id,
        )
        generated_roadmap = generate_roadmap_structure(
            context=context,
            final_roadmap_generation_prompt=final_prompt,
        )
        roadmap = persist_generated_roadmap(
            program=program,
            assignment_scope=assignment_scope,
            interns=interns,
            generated=generated_roadmap,
            created_by=mentor,
        )
        delete_preview(preview_id)
        return roadmap


def to_api_error_payload(exc: Exception) -> tuple[int, dict]:
    """Map service exceptions to HTTP status + safe JSON body."""
    if isinstance(exc, AIPermissionError):
        return 403, {"detail": exc.user_message}
    if isinstance(exc, AIValidationError):
        return 400, {"detail": exc.user_message}
    if isinstance(exc, AIServiceError):
        return 503, {"detail": exc.user_message}
    return 503, {
        "detail": "AI roadmap generation is currently unavailable. Please try again."
    }
