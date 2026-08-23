"""AI Weekly Report Prompt Builder — OpenAI call #1."""

from __future__ import annotations

import json
from typing import Any

from services.ai import client as openai_client
from services.ai import config
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedWeeklyReportPrompt

WEEKLY_REPORT_PROMPT_BUILDER_SYSTEM = """
You are an AI Prompt Builder for internship weekly performance reports.
Your job is NOT to write the weekly report.
Your job is to transform the supplied structured Intern + Week context into one
high-quality customized weekly-report-generation prompt for a second model.

Core rules for the prompt you produce:
- Analyze ONLY the selected Intern and selected Week.
- Compare planned week objectives/tasks against actual performance evidence.
- Base claims only on supplied system evidence.
- Do not fabricate achievements, completions, feedback, or scores.
- Do not exaggerate performance.
- Do not infer personality traits or motivation.
- Do not make hiring/employment recommendations.
- Do not compare against other interns or include other interns' data.
- Distinguish incomplete work from missing evidence.
- Treat Needs Revision as revision request, not automatic failure or score=0.
- Recognize improvement across multiple submission versions when evidence supports it.
- Use professional, constructive Mentor-facing language.
- Official Overall Weekly Score is Django-calculated and must not be invented.
- Unscored tasks must never be treated as zero.
- Additional Mentor Notes are manual and must not be generated.
- Do not instruct the generator to modify roadmaps, tasks, deadlines, or skills.

Required output fields:
- prompt_title
- weekly_report_generation_prompt
- important_constraints
- personalization_points
- missing_context_notes
""".strip()


def _validate_prompt_output(
    result: GeneratedWeeklyReportPrompt,
) -> GeneratedWeeklyReportPrompt:
    if not result.weekly_report_generation_prompt.strip():
        raise AIInvalidOutputError(
            "AI weekly report generation could not produce a valid prompt. Please try again."
        )
    if not result.prompt_title.strip():
        raise AIInvalidOutputError(
            "AI weekly report generation could not produce a valid prompt. Please try again."
        )
    return result


def build_weekly_report_prompt(context: dict[str, Any]) -> GeneratedWeeklyReportPrompt:
    """Call OpenAI to build a customized weekly-report generation prompt."""
    user_payload = {
        "role": "Weekly Report Prompt Builder request",
        "canonical_weekly_context": context,
        "required_output_fields": [
            "prompt_title",
            "weekly_report_generation_prompt",
            "important_constraints",
            "personalization_points",
            "missing_context_notes",
        ],
        "target_report_sections": [
            "performance_summary",
            "achievements",
            "learning_progress",
            "productivity_analysis",
            "mentor_focus_suggestions",
            "recommended_next_focus",
        ],
    }
    messages = [
        {"role": "system", "content": WEEKLY_REPORT_PROMPT_BUILDER_SYSTEM},
        {
            "role": "user",
            "content": json.dumps(user_payload, ensure_ascii=True, default=str),
        },
    ]

    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            parsed = openai_client.parse_structured(
                model=config.prompt_builder_model(),
                input_messages=messages,
                text_format=GeneratedWeeklyReportPrompt,
            )
            return _validate_prompt_output(parsed)
        except AIInvalidOutputError as exc:
            last_error = exc
            continue
    raise last_error or AIInvalidOutputError()
