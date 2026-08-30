"""Deterministically assemble the Final Roadmap Generation Prompt shown to mentors."""

from __future__ import annotations

from datetime import date
from typing import Any

from common.constants import RoadmapScope
from services.ai.roadmap_week_dates import format_authoritative_week_boundaries_block
from services.ai.schemas import GeneratedRoadmapPrompt


def _section(title: str, body: str) -> str:
    return f"\n{'=' * 30}\n{title}\n{'=' * 30}\n{body.strip()}\n"


def _bullets(items: list[str]) -> str:
    cleaned = [item.strip() for item in items if item and str(item).strip()]
    if not cleaned:
        return "- (none)\n"
    return "".join(f"- {item}\n" for item in cleaned)


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _week_boundaries_block(program: dict[str, Any]) -> str:
    start = _parse_iso_date(program.get("start_date"))
    end = _parse_iso_date(program.get("end_date"))
    duration = program.get("duration_weeks")
    try:
        duration_weeks = int(duration)
    except (TypeError, ValueError):
        duration_weeks = 0
    if start is None or end is None or duration_weeks < 1:
        return (
            "Week boundaries could not be derived from Program dates/duration. "
            "Respect Program start_date, end_date, and duration_weeks exactly.\n"
        )
    return format_authoritative_week_boundaries_block(
        program_start=start,
        program_end=end,
        duration_weeks=duration_weeks,
    )


def _program_block(program: dict[str, Any]) -> str:
    lines = [
        f"Program ID: {program.get('id')}",
        f"Title: {program.get('title')}",
        f"Description: {program.get('description')}",
        f"Role: {program.get('role')}",
        f"Department: {program.get('department')}",
        f"Start Date: {program.get('start_date')}",
        f"End Date: {program.get('end_date')}",
        f"Duration (weeks): {program.get('duration_weeks')}",
        f"Weekly Hours: {program.get('weekly_hours')}",
        f"Maximum Interns: {program.get('maximum_interns')}",
        f"Mentor: {(program.get('mentor') or {}).get('full_name')}",
        f"Goals: {program.get('goals') or '(not provided)'}",
        f"Skills Needed: {', '.join(program.get('skills_needed') or []) or '(not provided)'}",
        f"Skills to Develop: {', '.join(program.get('skills_to_develop') or []) or '(not provided)'}",
        f"Expected Outcome: {program.get('expected_outcome') or '(not provided)'}",
        f"Final Project: {program.get('final_project') or '(not provided)'}",
        f"Additional Instructions: {program.get('additional_instructions') or '(not provided)'}",
    ]
    return "\n".join(lines)


def _reference_block(materials: list[dict[str, Any]]) -> str:
    if not materials:
        return "No program reference materials were supplied.\n"

    parts: list[str] = []
    for index, material in enumerate(materials, start=1):
        header = (
            f"REFERENCE MATERIAL {index}\n"
            f"Title: {material.get('title')}\n"
            f"Type: {material.get('resource_type')}\n"
            f"File: {material.get('file_name') or '(none)'}\n"
            f"External URL: {material.get('external_url') or '(none)'}\n"
            f"Content Retrieved: {bool(material.get('content_retrieved'))}\n"
            f"Note: {material.get('content_note') or ''}\n"
        )
        if material.get("content_retrieved") and material.get("extracted_text"):
            header += (
                "\nRelevant Extracted Content:\n"
                f"{material.get('extracted_text')}\n"
            )
        else:
            header += (
                "\nRelevant Extracted Content:\n"
                "(Not available — do not pretend this reference content was analyzed.)\n"
            )
        parts.append(header)
    parts.append(
        "The supplied usable Reference Material is required source context for this roadmap. "
        "Use its relevant requirements, technologies, workflows, constraints, deliverables, "
        "testing requirements, and project-specific guidance when generating the roadmap. "
        "Do not ignore usable references. Do not copy irrelevant text. "
        "Before returning, verify each usable reference meaningfully influenced the roadmap "
        "wherever relevant.\n"
    )
    return "\n".join(parts)


def _scope_block(context: dict[str, Any]) -> str:
    scope = context.get("roadmap_scope")
    if scope == RoadmapScope.PROGRAM:
        return (
            "Assignment Scope: PROGRAM (Entire Program)\n"
            "- This roadmap applies to the Entire Program.\n"
            "- Use the full Program context and all relevant populated Program data.\n"
            "- Cover EVERY Program Skill to Develop meaningfully.\n"
            "- Respect Program Goals, Expected Outcome, Final Project, dates, duration, "
            "and Weekly Hours.\n"
            "- Meaningfully use supplied Reference Materials.\n"
            "- Do NOT create individual intern ownership inside task descriptions.\n"
            "- Do NOT invent named leads/owners (e.g. 'Faisal leads, Samir supports').\n"
            "- Use Entire Program / team-level wording where appropriate.\n"
            "- Individual personalization is not required for PROGRAM scope.\n"
        )
    if scope == RoadmapScope.GROUP:
        names = [item.get("full_name") for item in context.get("interns") or []]
        return (
            "Assignment Scope: GROUP\n"
            f"- Selected interns: {', '.join(n for n in names if n) or '(none)'}\n"
            "- Use full relevant Program context plus selected-intern profile context.\n"
            "- Cover every Program Skill to Develop meaningfully.\n"
            "- Do not fabricate named individual task ownership/leads unless explicitly "
            "supported by structured assignment data.\n"
        )
    # INDIVIDUAL
    intern = (context.get("interns") or [{}])[0]
    skill_lines = []
    for skill in intern.get("skills") or []:
        skill_lines.append(
            f"{skill.get('skill_name')}: level {skill.get('skill_level')} "
            f"({skill.get('skill_level_label')})"
        )
    focus = context.get("mentor_focus_skills") or []
    return (
        "Assignment Scope: INDIVIDUAL\n"
        f"- Selected Intern: {intern.get('full_name')}\n"
        f"- Major: {intern.get('major') or '(not provided)'}\n"
        f"- University: {intern.get('university') or '(not provided)'}\n"
        f"- Learning Goals: {intern.get('learning_goals') or '(not provided)'}\n"
        f"- Preferences: {intern.get('preferences_note')}\n"
        "- Current Intern Skills:\n"
        f"{_bullets(skill_lines) if skill_lines else '- (none listed)'}\n"
        "- Personalize learning objectives, progression, difficulty, task complexity, "
        "expected skills, technical depth, and learning emphasis using this Intern profile.\n"
        "- Use skill levels to avoid obviously inappropriate beginner/expert mismatch.\n"
        "- Still cover EVERY Program Skill to Develop meaningfully.\n"
        "- Mentor Focus Skills (optional extra emphasis; do NOT ignore other Program skills):\n"
        f"{_bullets(focus) if focus else '- (none selected)'}\n"
    )


def _quality_and_self_check() -> str:
    return (
        "QUALITY CONDITIONS\n"
        "1. Correct number of weeks matching Program duration.\n"
        "2. Sequential week progression.\n"
        "3. Program start/end dates respected.\n"
        "4. Task due dates within valid week/program boundaries.\n"
        "5. Realistic weekly workload aligned with Weekly Hours.\n"
        "6. Meaningful coverage of every Skill to Develop.\n"
        "7. Alignment with Program Goals.\n"
        "8. Alignment with Expected Outcome.\n"
        "9. Logical progression toward Final Project.\n"
        "10. Meaningful use of supplied usable Reference Materials.\n"
        "11. Enough hands-on technical work where the context supports it.\n"
        "12. Appropriate difficulty.\n"
        "13. Clear deliverables.\n"
        "14. Measurable success criteria.\n"
        "15. No unsupported technology assumptions.\n"
        "16. No obviously duplicated/repetitive tasks.\n"
        "17. No lifecycle-status words (DRAFT, PUBLISHED, ARCHIVED) in the title.\n"
        "18. Correct PROGRAM / GROUP / INDIVIDUAL behavior.\n"
        "19. Correct Individual personalization where required.\n"
        "20. Mentor Focus Skills receive extra emphasis when supplied.\n"
        "\n"
        "TECHNOLOGY ANTI-HALLUCINATION\n"
        "Technologies explicitly supplied by Program data or extracted Reference Material "
        "MAY and SHOULD be used specifically where relevant. Technologies not supported by "
        "the supplied context must not be invented as mandatory requirements.\n"
        "\n"
        "BEFORE RETURNING THE ROADMAP, VERIFY INTERNALLY THAT:\n"
        "1. All relevant supplied Program data was considered.\n"
        "2. Every Program Skill to Develop is meaningfully covered.\n"
        "3. Supplied usable Reference Material meaningfully influenced the roadmap "
        "wherever relevant.\n"
        "4. Applicable reference requirements were incorporated.\n"
        "5. Program dates and duration are respected.\n"
        "6. Weekly workload aligns with Weekly Hours.\n"
        "7. The roadmap logically progresses toward the Final Project.\n"
        "8. Program Goals and Expected Outcome are reflected.\n"
        "9. Scope-specific rules are respected.\n"
        "10. Individual personalization is applied where required.\n"
        "11. Mentor Focus Skills receive additional emphasis where supplied.\n"
        "12. No unsupported technology was invented.\n"
        "13. Tasks contain clear deliverables and measurable success criteria.\n"
        "14. All required roadmap schema fields are complete.\n"
    )


def build_final_roadmap_generation_prompt(
    *,
    context: dict[str, Any],
    prompt_builder_result: GeneratedRoadmapPrompt,
) -> str:
    """
    Assemble the exact semantic prompt the Mentor will review and Call #2 will receive.
    """
    program = context.get("program") or {}
    parts = [
        _section(
            "CUSTOMIZED ROADMAP GENERATION INSTRUCTIONS (FROM AI PROMPT BUILDER)",
            (
                f"Prompt Title: {prompt_builder_result.prompt_title}\n\n"
                f"{prompt_builder_result.roadmap_generation_prompt}\n\n"
                "Important Constraints from Prompt Builder:\n"
                f"{_bullets(prompt_builder_result.important_constraints)}\n"
                "Personalization Points from Prompt Builder:\n"
                f"{_bullets(prompt_builder_result.personalization_points)}\n"
                "Missing Context Notes from Prompt Builder:\n"
                f"{_bullets(prompt_builder_result.missing_context_notes)}\n"
            ),
        ),
        _section("AUTHORITATIVE PROGRAM DATA", _program_block(program)),
        _section(
            "AUTHORITATIVE ROADMAP WEEK BOUNDARIES",
            _week_boundaries_block(program),
        ),
        _section(
            "SKILLS TO DEVELOP — REQUIRED COVERAGE",
            (
                "Every item below MUST receive meaningful coverage in learning objectives, "
                "expected skills, and practical tasks where appropriate. Do not merely copy "
                "labels. Do not force every skill into every week. Coverage must be proportional "
                "and logical across the program duration.\n\n"
                f"{_bullets(program.get('skills_to_develop') or [])}"
            ),
        ),
        _section("ASSIGNMENT SCOPE RULES", _scope_block(context)),
        _section(
            "REFERENCE MATERIAL",
            _reference_block(context.get("reference_materials") or []),
        ),
        _section(
            "MENTOR-REQUESTED SKILLS TO FOCUS ON",
            (
                "Give these skills additional emphasis when creating this roadmap. "
                "They do NOT replace Program Skills to Develop.\n\n"
                f"{_bullets(context.get('mentor_focus_skills') or [])}"
                if context.get("roadmap_scope") == RoadmapScope.INDIVIDUAL
                else "Not applicable for this scope.\n"
            ),
        ),
        _section(
            "UNAVAILABLE / MISSING CONTEXT",
            _bullets(context.get("unavailable_data") or []),
        ),
        _section("ROADMAP QUALITY CONDITIONS AND FINAL SELF-CHECK", _quality_and_self_check()),
    ]
    return "\n".join(parts).strip() + "\n"
