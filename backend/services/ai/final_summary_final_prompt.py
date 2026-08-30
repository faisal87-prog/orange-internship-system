"""Deterministically assemble the Final Final-Summary Generation Prompt."""

from __future__ import annotations

from typing import Any

from services.ai.schemas import GeneratedFinalSummaryPrompt


def _section(title: str, body: str) -> str:
    return f"\n{'=' * 30}\n{title}\n{'=' * 30}\n{body.strip()}\n"


def _bullets(items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if item and str(item).strip()]
    if not cleaned:
        return "- (none)\n"
    return "".join(f"- {item}\n" for item in cleaned)


def _task_block(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return "No tasks assigned to this intern for this program.\n"
    parts: list[str] = []
    for index, task in enumerate(tasks, start=1):
        parts.append(
            f"TASK {index}: {task.get('title')}\n"
            f"Week: {task.get('week_number')}\n"
            f"Status: {task.get('status')}\n"
            f"Requirement: {task.get('requirement_type')}\n"
            f"Difficulty: {task.get('difficulty')}\n"
            f"Estimated minutes: {task.get('estimated_time_minutes')}\n"
            f"Due date: {task.get('due_date')}\n"
            f"Completed: {task.get('is_completed')}\n"
            f"Needs revision: {task.get('is_needs_revision')}\n"
            f"Score: {task.get('score') if task.get('score') is not None else '(no score)'}\n"
            f"Late submission: {task.get('is_late')}\n"
            f"Overdue: {task.get('is_overdue')}\n"
            f"Mentor feedback: {task.get('mentor_feedback') or '(none)'}\n"
            f"Deliverable: {task.get('deliverable') or '(none)'}\n"
            f"Success criteria: {task.get('success_criteria') or '(none)'}\n"
            f"Description: {task.get('description') or '(none)'}\n"
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
            for file_meta in submission.get("files") or []:
                parts.append(
                    f"  File: {file_meta.get('original_file_name')} "
                    f"({file_meta.get('file_type')})\n"
                )
    return "\n".join(parts)


def _week_block(weeks: list[dict[str, Any]]) -> str:
    if not weeks:
        return "No roadmap weeks available.\n"
    parts: list[str] = []
    for week in weeks:
        parts.append(
            f"WEEK {week.get('week_number')}: {week.get('weekly_focus')}\n"
            f"Dates: {week.get('start_date')} → {week.get('end_date')}\n"
            f"Mentor notes: {week.get('mentor_notes') or '(none)'}\n"
            "Learning objectives:\n"
            f"{_bullets(week.get('learning_objectives') or [])}"
            "Expected skills gained:\n"
            f"{_bullets(week.get('expected_skills_gained') or [])}"
        )
    return "\n".join(parts)


def _weekly_report_block(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return "No approved weekly reports available.\n"
    parts: list[str] = []
    for report in reports:
        achievements = report.get("achievements") or []
        if isinstance(achievements, list):
            achievements_text = _bullets([str(item) for item in achievements])
        else:
            achievements_text = str(achievements)
        focus = report.get("mentor_focus_suggestions") or []
        if isinstance(focus, list):
            focus_text = _bullets([str(item) for item in focus])
        else:
            focus_text = str(focus)
        parts.append(
            f"APPROVED WEEKLY REPORT — Week {report.get('week_number')}\n"
            f"Overall weekly score: "
            f"{report.get('overall_weekly_score') if report.get('overall_weekly_score') is not None else '(none)'}\n"
            f"Performance summary: {report.get('performance_summary') or '(none)'}\n"
            f"Achievements:\n{achievements_text}"
            f"Learning progress: {report.get('learning_progress') or '(none)'}\n"
            f"Productivity analysis: {report.get('productivity_analysis') or '(none)'}\n"
            f"Mentor focus suggestions:\n{focus_text}"
            f"Recommended next focus: {report.get('recommended_next_focus') or '(none)'}\n"
            f"Additional mentor notes: {report.get('additional_mentor_notes') or '(none)'}\n"
        )
    return "\n".join(parts)


def build_final_final_summary_generation_prompt(
    *,
    context: dict[str, Any],
    prompt_builder_result: GeneratedFinalSummaryPrompt,
) -> str:
    program = context.get("program") or {}
    intern = context.get("intern") or {}
    roadmap = context.get("roadmap") or {}
    score = context.get("score_context") or {}
    skills = []
    for skill in intern.get("skills") or []:
        skills.append(
            f"{skill.get('skill_name')}: level {skill.get('skill_level')} "
            f"({skill.get('skill_level_label')})"
        )

    parts = [
        _section(
            "CUSTOMIZED FINAL SUMMARY INSTRUCTIONS (FROM AI PROMPT BUILDER)",
            (
                f"Prompt Title: {prompt_builder_result.prompt_title}\n\n"
                f"{prompt_builder_result.final_summary_generation_prompt}\n\n"
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
                    f"Description: {program.get('description') or '(not provided)'}",
                    f"Role: {program.get('role')}",
                    f"Department: {program.get('department')}",
                    f"Dates: {program.get('start_date')} → {program.get('end_date')}",
                    f"Duration weeks: {program.get('duration_weeks')}",
                    f"Weekly Hours: {program.get('weekly_hours')}",
                    f"Goals: {program.get('goals') or '(not provided)'}",
                    f"Skills Needed: {', '.join(program.get('skills_needed') or []) or '(none)'}",
                    f"Skills to Develop: {', '.join(program.get('skills_to_develop') or []) or '(none)'}",
                    f"Expected Outcome: {program.get('expected_outcome') or '(not provided)'}",
                    f"Final Project: {program.get('final_project') or '(not provided)'}",
                    f"Additional Instructions: {program.get('additional_instructions') or '(none)'}",
                ]
            ),
        ),
        _section(
            "INTERN CONTEXT",
            "\n".join(
                [
                    f"ID: {intern.get('id')}",
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
            "ROADMAP CONTEXT (PLANNED)",
            (
                "\n".join(
                    [
                        f"Title: {roadmap.get('title')}",
                        f"Summary: {roadmap.get('summary') or '(none)'}",
                        f"Status: {roadmap.get('status')}",
                        f"Scope: {roadmap.get('assignment_scope')}",
                        f"Number of weeks: {roadmap.get('number_of_weeks')}",
                    ]
                )
                if roadmap
                else "No roadmap available."
            ),
        ),
        _section("ROADMAP WEEKS", _week_block(context.get("weeks") or [])),
        _section(
            "ACTUAL TASK / SUBMISSION / REVIEW EVIDENCE (FULL INTERNSHIP)",
            _task_block(context.get("tasks") or []),
        ),
        _section(
            "APPROVED WEEKLY REPORTS (SUPPORTING EVIDENCE ONLY)",
            _weekly_report_block(context.get("weekly_reports") or []),
        ),
        _section(
            "SCORE CONTEXT (SUPPORTING ONLY — FINAL SCORE IS DJANGO CALCULATED)",
            (
                f"Scored task count: {score.get('scored_task_count')}\n"
                f"Task score values: {score.get('score_values')}\n"
                f"Approved weekly scores: {score.get('approved_weekly_scores')}\n"
                f"Django Final Score: {score.get('django_final_score_display')}\n"
                f"Scored weekly report count: {score.get('scored_weekly_report_count')}\n"
                f"Note: {score.get('note')}\n"
                "Do NOT invent or output an official Final Score.\n"
            ),
        ),
        _section(
            "MANDATORY FINAL SUMMARY RULES",
            (
                "Produce ONLY these string fields:\n"
                "- internship_introduction\n"
                "- training_summary\n"
                "- overall_performance_summary\n"
                "- learning_journey\n"
                "- main_achievements\n"
                "- goal_achievement\n"
                "- final_performance_summary\n\n"
                "internship_introduction: concise Program purpose/idea only. "
                "Do NOT discuss Intern performance.\n"
                "training_summary: brief overview of training areas covered, "
                "type of work, technical/learning areas, Program progression, "
                "and relationship to the Final Project.\n"
                "Do NOT output final_score.\n"
                "Do NOT output mentor_comments.\n"
                "Do NOT output additional_notes / additional_mentor_notes.\n"
                "Do NOT output week/task tables or Mentor Signature.\n"
                "Do NOT output Strengths, Areas for Improvement, or hiring recommendations.\n"
                "Do NOT invent progress when evidence is missing.\n"
                "Evaluate Program Goals / Skills to Develop / Expected Outcome / Final Project "
                "against available evidence (achieved, partially demonstrated, or cannot verify).\n"
                "Analyze only this Intern across the full internship.\n"
            ),
        ),
        _section(
            "UNAVAILABLE / MISSING CONTEXT",
            _bullets(context.get("unavailable_data") or []),
        ),
    ]
    return "\n".join(parts).strip() + "\n"
