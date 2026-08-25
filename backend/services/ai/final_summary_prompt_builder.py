"""AI Final Summary Prompt Builder — OpenAI call #1."""

from __future__ import annotations

import json
from typing import Any

from services.ai import client as openai_client
from services.ai import config
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedFinalSummaryPrompt

FINAL_SUMMARY_PROMPT_BUILDER_SYSTEM = """
You are an AI Prompt Builder for final internship summaries.
Your job is NOT to write the final summary.
Your job is to transform the supplied structured Intern + Program context into one
high-quality customized final-summary-generation prompt for a second model.

Core rules for the prompt you produce:
- Analyze ONLY the selected Intern across the FULL internship period.
- Compare planned Program Goals, Skills to Develop, Expected Outcome, Final Project,
  and Roadmap objectives against actual evidence.
- Base claims only on supplied system evidence.
- Do not fabricate achievements, completions, feedback, scores, or improvement.
- Do not invent a Final Score.
- Do not treat unscored tasks as zero.
- Treat Needs Revision as revision history, not automatic failure.
- Recognize improvement across multiple submission versions when evidence supports it.
- Recognize progression across weeks when evidence supports it.
- Distinguish missing evidence from poor performance.
- Do not infer personality traits.
- Do not make hiring/employment recommendations.
- Do not compare against other interns or include other interns' data.
- Approved Weekly Reports are supporting evidence only; task/submission records are authoritative.
- Mentor Comments and Additional Notes are manual and must not be generated.
- Instruct the generator to produce ONLY these five string sections:
  overall_performance_summary, learning_journey, main_achievements,
  goal_achievement, final_performance_summary.
- Do not instruct Strengths, Areas for Improvement, or hiring sections.

Required output fields:
- prompt_title
- final_summary_generation_prompt
- important_constraints
- personalization_points
- missing_context_notes
""".strip()


def _validate_prompt_output(
    result: GeneratedFinalSummaryPrompt,
) -> GeneratedFinalSummaryPrompt:
    if not result.final_summary_generation_prompt.strip():
        raise AIInvalidOutputError(
            "AI final summary generation could not produce a valid prompt. Please try again."
        )
    if not result.prompt_title.strip():
        raise AIInvalidOutputError(
            "AI final summary generation could not produce a valid prompt. Please try again."
        )
    return result


def build_final_summary_prompt(context: dict[str, Any]) -> GeneratedFinalSummaryPrompt:
    """Call OpenAI to build a customized final-summary generation prompt."""
    user_payload = {
        "role": "Final Summary Prompt Builder request",
        "canonical_final_summary_context": context,
        "required_output_fields": [
            "prompt_title",
            "final_summary_generation_prompt",
            "important_constraints",
            "personalization_points",
            "missing_context_notes",
        ],
        "target_summary_sections": [
            "overall_performance_summary",
            "learning_journey",
            "main_achievements",
            "goal_achievement",
            "final_performance_summary",
        ],
    }
    messages = [
        {"role": "system", "content": FINAL_SUMMARY_PROMPT_BUILDER_SYSTEM},
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
                text_format=GeneratedFinalSummaryPrompt,
            )
            return _validate_prompt_output(parsed)
        except AIInvalidOutputError as exc:
            last_error = exc
            continue
    raise last_error or AIInvalidOutputError()
