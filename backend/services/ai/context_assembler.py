"""Deterministic roadmap context assembler (trusted DB data only)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from apps.programs.models import InternshipProgram, InternProfile, ProgramReferenceMaterial
from common.constants import RoadmapScope
from services.ai.exceptions import AIPermissionError, AIValidationError
from services.ai.reference_extractor import extract_reference_material

SKILL_LEVEL_LABELS = {
    1: "Beginner",
    2: "Basic",
    3: "Intermediate",
    4: "Advanced",
    5: "Expert",
}


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def serialize_reference(material: ProgramReferenceMaterial) -> dict[str, Any]:
    payload = {
        "id": material.id,
        "title": material.title,
        "resource_type": material.resource_type,
        "has_file": bool(material.file),
        "file_name": Path(material.file.name).name if material.file else None,
        "external_url": material.external_url or None,
    }
    extraction = extract_reference_material(material)
    payload.update(
        {
            "content_retrieved": extraction["content_retrieved"],
            "extracted_text": extraction.get("extracted_text"),
            # Keep content_preview alias for compatibility with prompt/generator payloads.
            "content_preview": extraction.get("extracted_text"),
            "content_note": extraction.get("content_note"),
        }
    )
    return payload


def serialize_intern(profile: InternProfile) -> dict[str, Any]:
    skills = []
    for skill in profile.skills.all():
        level = int(skill.skill_level)
        skills.append(
            {
                "skill_name": skill.skill_name,
                "skill_level": level,
                "skill_level_label": SKILL_LEVEL_LABELS.get(level, str(level)),
            }
        )
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


def _normalize_focus_skills(
    *,
    assignment_scope: str,
    mentor_focus_skills: list[str] | None,
) -> list[str]:
    if assignment_scope != RoadmapScope.INDIVIDUAL:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in mentor_focus_skills or []:
        value = " ".join(str(raw).split()).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def assemble_roadmap_context(
    *,
    program: InternshipProgram,
    assignment_scope: str,
    interns: list[InternProfile],
    mentor_focus_skills: list[str] | None = None,
) -> dict[str, Any]:
    """Build the canonical structured context used by both AI stages."""
    materials = [
        serialize_reference(item)
        for item in program.reference_materials.all().order_by("id")
    ]
    intern_payloads = [serialize_intern(intern) for intern in interns]
    focus_skills = _normalize_focus_skills(
        assignment_scope=assignment_scope,
        mentor_focus_skills=mentor_focus_skills,
    )

    unavailable: list[str] = []
    if not materials:
        unavailable.append("No program reference materials are available.")
    for material in materials:
        if material.get("has_file") and not material.get("content_retrieved"):
            unavailable.append(
                material.get("content_note")
                or f"Reference '{material.get('title')}' could not be extracted."
            )
        if material.get("external_url") and not material.get("has_file"):
            unavailable.append(
                f"External URL supplied for '{material.get('title')}'; "
                "webpage content was not extracted."
            )
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
        "mentor_focus_skills": focus_skills,
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
            "cover_every_skills_to_develop_item": True,
            "use_reference_materials_meaningfully": True,
        },
        "unavailable_data": unavailable,
        "instructions_for_ai": {
            "use_only_supplied_context": True,
            "do_not_invent_missing_facts": True,
            "external_urls_are_metadata_only_unless_content_retrieved": True,
            "do_not_ignore_usable_reference_materials": True,
        },
    }
