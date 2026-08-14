"""AI Prompt Builder — OpenAI call #1 for roadmap generation."""

from __future__ import annotations

import json
from typing import Any

from services.ai import client as openai_client
from services.ai import config
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import GeneratedRoadmapPrompt

PROMPT_BUILDER_SYSTEM = """
You are an AI Prompt Builder for an internship management platform.
Your job is NOT to generate a roadmap.
Your job is to transform the supplied structured program/intern context into one
high-quality customized roadmap-generation prompt for a second model.

Core rules:
- Use ONLY the supplied context. Do not invent program facts or unsupported technologies.
- Adapt instructions to program role, duration, weekly hours, skills, goals,
  expected outcome, final project, department, and roadmap scope.
- Personalize using intern profiles when present; if data is missing, note it
  in missing_context_notes instead of inventing it.
- External reference URLs are metadata only unless content_retrieved is true.
- Require multiple meaningful tasks per week, progressive learning, realistic
  workload guidance using weekly_hours, measurable deliverables, and success criteria.
- Require valid difficulty values: EASY, MEDIUM, HARD.
- Require valid requirement_type values: REQUIRED, OPTIONAL.
- Require due dates within the program date range and week boundaries.
- Do not make hiring/employment decisions.
- Do not include secrets, API keys, or system credentials in the prompt.
- The field roadmap_generation_prompt must be a complete instruction prompt
  that the Roadmap Generator can follow.

Skills-to-develop coverage (mandatory):
- Every item in program.skills_to_develop MUST be intentionally addressed somewhere
  in the roadmap.
- For each skill: require meaningful appearance in at least one week's learning
  objectives or expected_skills_gained, and support with at least one relevant task
  where appropriate.
- Coverage must be proportional to duration and goals; do NOT force every skill
  into every week.
- Do not merely copy skill labels without corresponding learning/work.
- Instruct the Roadmap Generator to explicitly verify coverage of ALL
  skills_to_develop before returning the final roadmap.
- Also strengthen alignment with Goals, Expected Outcome, Final Project,
  Skills Needed, and Role so the roadmap clearly traces back to Program config.

Technical concreteness:
- Keep some planning/review checkpoints, but ensure enough hands-on technical
  learning and implementation work when the Program data supports it.
- Prefer concrete work such as programming, backend/frontend implementation,
  API integration, AI integration, prompt/behavior evaluation, structured outputs,
  testing, debugging, and system integration WHEN those areas are supported by
  the supplied context.
- NEVER hallucinate technologies that were never supplied in the Program,
  intern, or reference context (for example do not assume Next.js or Django
  unless they appear in the supplied context).
- If a technology is explicitly listed (e.g. Python under skills_to_develop),
  the roadmap SHOULD include related learning/tasks.

Title rules:
- The roadmap title must NOT include lifecycle/status words such as DRAFT,
  PUBLISHED, or ARCHIVED.
- Status is controlled by the application UI separately.
- Prefer a clean descriptive title (program/role/duration).

Roadmap scope / assignee rules:
- If roadmap_scope is PROGRAM: do NOT assign named individual interns as task
  owners/leads inside task titles or descriptions. Do not invent individual
  division of responsibility. Tasks apply to the Entire Program. Descriptions
  may refer generically to "the interns", "the team", or collaborative work.
- If roadmap_scope is GROUP: personalize to the selected group, but do not
  fabricate individual task ownership/leads unless explicitly supported.
- If roadmap_scope is INDIVIDUAL: personalize tasks to the selected intern.

Quality checklist the generated prompt must require the Roadmap Generator to verify:
1. Correct number of weeks matching duration_weeks
2. Sequential week numbers
3. Program date compliance
4. Realistic weekly workload near weekly_hours
5. Coverage of every skills_to_develop item
6. Alignment with Goals
7. Alignment with Expected Outcome
8. Progression toward Final Project
9. Relevant technical implementation work (when supported by context)
10. No unsupported technology assumptions
11. No lifecycle status words in the title
12. PROGRAM scope does not invent individual assignees
13. All required task fields present
14. No obviously duplicate tasks
""".strip()


def _validate_prompt_output(result: GeneratedRoadmapPrompt) -> GeneratedRoadmapPrompt:
    if not result.roadmap_generation_prompt or not result.roadmap_generation_prompt.strip():
        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
        )
    if not result.prompt_title or not result.prompt_title.strip():
        raise AIInvalidOutputError(
            "AI roadmap generation could not produce a valid roadmap. Please try again."
        )
    return result


def build_roadmap_prompt(context: dict[str, Any]) -> GeneratedRoadmapPrompt:
    """
    Call OpenAI to build a customized roadmap-generation prompt.

    Retries once on invalid structured output.
    """
    skills = context.get("program", {}).get("skills_to_develop") or []
    user_payload = {
        "role": "Roadmap Prompt Builder request",
        "canonical_context": context,
        "mandatory_skills_to_cover": skills,
        "roadmap_scope": context.get("roadmap_scope"),
        "quality_checklist": [
            "cover_every_skills_to_develop_item",
            "align_with_goals_expected_outcome_final_project",
            "include_concrete_technical_work_when_supported",
            "no_unsupported_technologies",
            "no_status_words_in_title",
            "program_scope_no_named_assignees",
            "verify_checklist_before_returning",
        ],
        "required_output_fields": [
            "prompt_title",
            "roadmap_generation_prompt",
            "important_constraints",
            "personalization_points",
            "missing_context_notes",
        ],
    }
    messages = [
        {"role": "system", "content": PROMPT_BUILDER_SYSTEM},
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
                text_format=GeneratedRoadmapPrompt,
            )
            return _validate_prompt_output(parsed)
        except AIInvalidOutputError as exc:
            last_error = exc
            continue
    raise last_error or AIInvalidOutputError()
