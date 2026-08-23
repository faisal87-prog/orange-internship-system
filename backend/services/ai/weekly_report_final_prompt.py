"""Deterministically assemble the Final Weekly Report Generation Prompt."""

from __future__ import annotations

from typing import Any

from services.ai.schemas import GeneratedWeeklyReportPrompt


def _section(title: str, body: str) -> str:
    return f"\n{'=' * 30}\n{title}\n{'=' * 30}\n{body.strip()}\n"


def _bullets(items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if item and str(item).strip()]
    if not cleaned:
        return "- (none)\n"
    return "".join(f"- {item}\n" for item in cleaned)


def _task_block(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "No tasks assigned to this intern for this week.\n"
    parts: list[str] = []
    for index, task in enumerate(tasks, start=1):
        parts.append(
            f"TASK {index}: {task.get('title')}\n"
            f"Status: {task.get('status')}\n"
            f"Requirement: {task.get('requirement_type')}\n"
            f"Difficulty: {task.get('difficulty')}\n"
            f"Due date: {task.get('due_date')}\n"
            f"Completed: {task.get('is_completed')}\n"
            f"Needs revision: {task.get('is_needs_revision')}\n"
            f"Score: {task.get('score') if task.get('score') is not None else '(no score)'}\n"
            f"Late submission: {task.get('is_late')}\n"
            f"Overdue: {task.get('is_overdue')}\n"
            f"Mentor feedback: {task.get('mentor_feedback') or '(none)'}\n"
            f"Deliverable: {task.get('deliverable') or '(none)'}\n"
            f"Success criteria: {task.get('success_criteria') or '(none)'}\n"
            f"Submission versions: {task.get('submission_count')}\n"
        )
        for submission in task.get("submissions") or []:
            parts.append(
                f"  Version {submission.get('version_number')} "
                f"at {submission.get('submitted_at')}\n"
                f"  Written response: {submission.get('written_response') or '(none)'}\n"
                f"  Notes: {submission.get('intern_notes') or '(none)'}\n"
                f"  External URL: {submission.get('external_url') or '(none)'}\n"
            )
    return "\n".join(parts)


def build_final_weekly_report_generation_prompt(
    *,
    context: dict[str, Any],
    prompt_builder_result: GeneratedWeeklyReportPrompt,
) -> str:
    program = context.get("program") or {}
    intern = context.get("intern") or {}
    week = context.get("week") or {}
    score = context.get("weekly_score") or {}
    skills = []
    for skill in intern.get("skills") or []:
        skills.append(
            f"{skill.get('skill_name')}: level {skill.get('skill_level')} "
            f"({skill.get('skill_level_label')})"
        )

    parts = [
        _section(
            "CUSTOMIZED WEEKLY REPORT INSTRUCTIONS (FROM AI PROMPT BUILDER)",
            (
                f"Prompt Title: {prompt_builder_result.prompt_title}\n\n"
                f"{prompt_builder_result.weekly_report_generation_prompt}\n\n"
                "Important Constraints from Prompt Builder:\n"
                f"{_bullets(prompt_builder_result.important_constraints)}\n"
                "Personalization Points from Prompt Builder:\n"
                f"{_bullets(prompt_builder_result.personalization_points)}\n"
                "Missing Context Notes from Prompt Builder:\n"
                f"{_bullets(prompt_builder_result.missing_context_notes)}\n"
            ),
        ),
        _section(
            "PROGRAM CONTEXT",
            "\n".join(
                [
                    f"Title: {program.get('title')}",
                    f"Role: {program.get('role')}",
                    f"Department: {program.get('department')}",
                    f"Dates: {program.get('start_date')} → {program.get('end_date')}",
                    f"Weekly Hours: {program.get('weekly_hours')}",
                    f"Goals: {program.get('goals') or '(not provided)'}",
                    f"Skills to Develop: {', '.join(program.get('skills_to_develop') or []) or '(none)'}",
                    f"Expected Outcome: {program.get('expected_outcome') or '(not provided)'}",
                    f"Final Project: {program.get('final_project') or '(not provided)'}",
                ]
            ),
        ),
        _section(
            "INTERN CONTEXT",
            "\n".join(
                [
                    f"Name: {intern.get('full_name')}",
                    f"Major: {intern.get('major') or '(not provided)'}",
                    f"University: {intern.get('university') or '(not provided)'}",
                    f"Learning Goals: {intern.get('learning_goals') or '(not provided)'}",
                    "Current Skills:",
                    _bullets(skills) if skills else "- (none listed)",
                ]
            ),
        ),
        _section(
            "ROADMAP WEEK CONTEXT (PLANNED)",
            "\n".join(
                [
                    f"Week Number: {week.get('week_number')}",
                    f"Weekly Focus: {week.get('weekly_focus')}",
                    f"Date Range: {week.get('start_date')} → {week.get('end_date')}",
                    f"Mentor Notes: {week.get('mentor_notes') or '(none)'}",
                    "Learning Objectives:",
                    _bullets(week.get("learning_objectives") or []),
                    "Expected Skills Gained:",
                    _bullets(week.get("expected_skills_gained") or []),
                ]
            ),
        ),
        _section(
            "ACTUAL TASK / SUBMISSION / REVIEW EVIDENCE",
            _task_block(context.get("tasks") or []),
        ),
        _section(
            "OVERALL WEEKLY SCORE (DJANGO CALCULATED)",
            (
                f"Score display: {score.get('display')}\n"
                f"Numeric score: {score.get('overall_weekly_score')}\n"
                f"Scored task count: {score.get('scored_task_count')}\n"
                f"Score values used: {score.get('score_values')}\n"
                f"Note: {score.get('calculation_note')}\n"
                "Do NOT invent or recalculate the official score.\n"
            ),
        ),
        _section(
            "MANDATORY REPORT RULES",
            (
                "Produce ONLY these string fields:\n"
                "- performance_summary\n"
                "- achievements\n"
                "- learning_progress\n"
                "- productivity_analysis\n"
                "- mentor_focus_suggestions\n"
                "- recommended_next_focus\n\n"
                "Do NOT output overall_weekly_score.\n"
                "Do NOT output additional_mentor_notes.\n"
                "Do NOT invent progress when evidence is missing.\n"
                "Do NOT modify roadmap/tasks.\n"
                "Analyze only this Intern and this Week.\n"
            ),
        ),
        _section(
            "UNAVAILABLE / MISSING CONTEXT",
            _bullets(context.get("unavailable_data") or []),
        ),
    ]
    return "\n".join(parts).strip() + "\n"
