"""Deterministic roadmap context assembler (trusted DB data only)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from apps.programs.models import InternshipProgram, InternProfile, ProgramReferenceMaterial
from common.constants import RoadmapScope
from services.ai.exceptions import AIPermissionError, AIValidationError

# Conservative text preview for local txt/csv only.
_TEXT_PREVIEW_EXTENSIONS = {".txt", ".csv"}
_TEXT_PREVIEW_MAX_CHARS = 4000


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _safe_text_preview(material: ProgramReferenceMaterial) -> dict[str, Any]:
    """Optionally include a short local text preview; never invent URL content."""
    result: dict[str, Any] = {
        "content_retrieved": False,
        "content_preview": None,
        "content_note": "Linked or binary content was not retrieved for this MVP.",
    }
    if not material.file:
        if material.external_url:
            result["content_note"] = (
                "External URL metadata only; linked page content was not fetched."
            )
        return result

    name = Path(material.file.name).name
    ext = Path(name).suffix.lower()
    if ext not in _TEXT_PREVIEW_EXTENSIONS:
        result["content_note"] = (
            f"Local file '{name}' is attached but binary/document content was not "
            "extracted for this MVP."
        )
        return result

    try:
        with material.file.open("rb") as handle:
            raw = handle.read(_TEXT_PREVIEW_MAX_CHARS + 1)
        text = raw.decode("utf-8", errors="replace")
        truncated = len(text) > _TEXT_PREVIEW_MAX_CHARS
        preview = text[:_TEXT_PREVIEW_MAX_CHARS]
        result.update(
            {
                "content_retrieved": True,
                "content_preview": preview,
                "content_note": (
                    "Local text preview included (truncated)."
                    if truncated
                    else "Local text preview included."
                ),
            }
        )
    except Exception:  # noqa: BLE001
        result["content_note"] = "Local file could not be read for preview."
    return result


def serialize_reference(material: ProgramReferenceMaterial) -> dict[str, Any]:
    payload = {
        "id": material.id,
        "title": material.title,
        "resource_type": material.resource_type,
        "has_file": bool(material.file),
        "file_name": Path(material.file.name).name if material.file else None,
        "external_url": material.external_url or None,
    }
    payload.update(_safe_text_preview(material))
    return payload


def serialize_intern(profile: InternProfile) -> dict[str, Any]:
    skills = [
        {"skill_name": skill.skill_name, "skill_level": skill.skill_level}
        for skill in profile.skills.all()
    ]
    return {
        "id": profile.id,
        "full_name": profile.user.full_name,
        "major": profile.major or None,
        "university": profile.university or None,
        "learning_goals": profile.learning_goals or None,
        "skills": skills,
        "preferences": None,
        "preferences_note": (
            "No preference field exists on the current intern profile model; "
            "do not invent preferences."
        ),
    }


def resolve_scope_interns(
    *,
    program: InternshipProgram,
    assignment_scope: str,
    selected_intern_ids: list[int] | None,
    mentor_id: int,
) -> list[InternProfile]:
    if program.mentor_id != mentor_id:
        raise AIPermissionError()

    selected_intern_ids = selected_intern_ids or []
    program_interns = InternProfile.objects.filter(program=program).prefetch_related(
        "skills", "user"
    )

    if assignment_scope == RoadmapScope.PROGRAM:
        return list(program_interns.order_by("user__full_name"))

    if assignment_scope == RoadmapScope.GROUP:
        if not selected_intern_ids:
            raise AIValidationError(
                "Group scope requires at least one selected intern."
            )
        interns = list(
            program_interns.filter(id__in=selected_intern_ids).order_by("user__full_name")
        )
        if len(interns) != len(set(selected_intern_ids)):
            raise AIValidationError(
                "One or more selected interns do not belong to this program."
            )
        return interns

    if assignment_scope == RoadmapScope.INDIVIDUAL:
        if len(selected_intern_ids) != 1:
            raise AIValidationError(
                "Individual scope requires exactly one selected intern."
            )
        intern = program_interns.filter(id=selected_intern_ids[0]).first()
        if intern is None:
            raise AIValidationError(
                "The selected intern does not belong to this program."
            )
        return [intern]

    raise AIValidationError("Invalid roadmap scope.")


def assemble_roadmap_context(
    *,
    program: InternshipProgram,
    assignment_scope: str,
    interns: list[InternProfile],
) -> dict[str, Any]:
    """Build the canonical structured context used by both AI stages."""
    materials = [
        serialize_reference(item)
        for item in program.reference_materials.all().order_by("id")
    ]
    intern_payloads = [serialize_intern(intern) for intern in interns]

    unavailable: list[str] = []
    if not materials:
        unavailable.append("No program reference materials are available.")
    if assignment_scope == RoadmapScope.PROGRAM and not interns:
        unavailable.append(
            "No interns are currently assigned to this program; generate a "
            "program-level roadmap without intern personalization."
        )
    unavailable.append(
        "Intern preference data is not available in the database; "
        "do not invent preferences."
    )

    return {
        "program": {
            "id": program.id,
            "title": program.title,
            "description": program.description,
            "role": program.role,
            "start_date": _iso(program.start_date),
            "end_date": _iso(program.end_date),
            "duration_weeks": program.duration_weeks,
            "skills_to_develop": program.skills_to_develop or [],
            "goals": program.goals or "",
            "skills_needed": program.skills_needed or [],
            "expected_outcome": program.expected_outcome or "",
            "final_project": program.final_project or "",
            "mentor": {
                "id": program.mentor_id,
                "full_name": program.mentor.full_name,
            },
            "department": program.department,
            "weekly_hours": program.weekly_hours,
            "maximum_interns": program.maximum_interns,
            "additional_instructions": program.additional_instructions or "",
            "status": program.status,
        },
        "roadmap_scope": assignment_scope,
        "interns": intern_payloads,
        "reference_materials": materials,
        "constraints": {
            "duration_weeks": program.duration_weeks,
            "weekly_hours": program.weekly_hours,
            "program_start_date": _iso(program.start_date),
            "program_end_date": _iso(program.end_date),
            "require_multiple_tasks_per_week": True,
            "require_progressive_learning": True,
            "do_not_make_hiring_decisions": True,
            "task_source_must_be_ai_generated_on_save": True,
        },
        "unavailable_data": unavailable,
        "instructions_for_ai": {
            "use_only_supplied_context": True,
            "do_not_invent_missing_facts": True,
            "external_urls_are_metadata_only_unless_content_retrieved": True,
        },
    }
