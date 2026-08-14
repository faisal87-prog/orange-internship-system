"""Orchestrate AI roadmap generation: context → prompt → generate → validate → save."""

from __future__ import annotations

from apps.programs.models import InternshipProgram
from apps.roadmaps.models import Roadmap
from common.constants import Role
from services.ai import config
from services.ai.context_assembler import assemble_roadmap_context, resolve_scope_interns
from services.ai.exceptions import AIPermissionError, AIServiceError, AIValidationError
from services.ai.generators import generate_roadmap_structure
from services.ai.logging_utils import generation_timer
from services.ai.persistence import persist_generated_roadmap
from services.ai.prompt_builder import build_roadmap_prompt


def generate_ai_roadmap(
    *,
    mentor,
    program_id: int,
    assignment_scope: str,
    selected_intern_ids: list[int] | None = None,
) -> Roadmap:
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
            selected_intern_ids=selected_intern_ids,
            mentor_id=mentor.id,
        )
        context = assemble_roadmap_context(
            program=program,
            assignment_scope=assignment_scope,
            interns=interns,
        )
        generated_prompt = build_roadmap_prompt(context)
        generated_roadmap = generate_roadmap_structure(
            context=context,
            generated_prompt=generated_prompt,
        )
        return persist_generated_roadmap(
            program=program,
            assignment_scope=assignment_scope,
            interns=interns,
            generated=generated_roadmap,
            created_by=mentor,
        )


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
