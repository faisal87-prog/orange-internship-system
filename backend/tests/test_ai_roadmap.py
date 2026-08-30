"""AI roadmap two-step generation tests — OpenAI is fully mocked (no real API calls)."""

from datetime import date, timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MentorProfile, User
from apps.programs.models import InternProfile, InternSkill, InternshipProgram, ProgramReferenceMaterial
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.tasks.models import Task, TaskAssignment
from common.constants import ProgramStatus, ResourceType, Role, RoadmapScope, RoadmapStatus, TaskSource
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import (
    GeneratedRoadmap,
    GeneratedRoadmapPrompt,
    GeneratedTask,
    GeneratedWeek,
)
from services.ai.validators import validate_generated_roadmap


PROMPT_URL = "/api/roadmaps/generate/prompt/"
CONTINUE_URL = "/api/roadmaps/generate/continue/"


def _week_payload(week_number: int, start: date, end: date, tasks: int = 2) -> GeneratedWeek:
    due = start + timedelta(days=min(2, max((end - start).days, 0)))
    if due > end:
        due = end
    return GeneratedWeek(
        week_number=week_number,
        weekly_focus=f"Week {week_number} focus",
        learning_objectives=[f"Objective {week_number}.1", f"Objective {week_number}.2"],
        expected_skills_gained=[f"Skill {week_number}"],
        mentor_notes="Review progress",
        tasks=[
            GeneratedTask(
                title=f"Task {week_number}.{index}",
                description=f"Description {week_number}.{index}",
                difficulty="EASY" if index == 1 else "MEDIUM",
                estimated_time_minutes=60 * index,
                deliverable=f"Deliverable {week_number}.{index}",
                success_criteria=f"Criteria {week_number}.{index}",
                due_date=due.isoformat(),
                requirement_type="REQUIRED" if index == 1 else "OPTIONAL",
            )
            for index in range(1, tasks + 1)
        ],
    )


def build_valid_roadmap(program: InternshipProgram) -> GeneratedRoadmap:
    from services.ai.validators import week_boundaries

    aligned = []
    for week_number in range(1, program.duration_weeks + 1):
        start, end = week_boundaries(
            program.start_date,
            program.end_date,
            week_number,
            program.duration_weeks,
        )
        aligned.append(_week_payload(week_number, start, end, tasks=2))
    return GeneratedRoadmap(
        title=f"{program.title} AI Roadmap",
        summary="AI generated draft roadmap for mentor review.",
        number_of_weeks=program.duration_weeks,
        weeks=aligned,
    )


def build_prompt() -> GeneratedRoadmapPrompt:
    return GeneratedRoadmapPrompt(
        prompt_title="Custom roadmap prompt",
        roadmap_generation_prompt=(
            "Generate a progressive internship roadmap with multiple tasks per week. "
            "Cover every skills_to_develop item. "
            "For PROGRAM scope do not invent named assignees. "
            "Do not put DRAFT in the title. "
            "Use Django REST Framework from the supplied reference."
        ),
        important_constraints=[
            "Respect duration_weeks",
            "Respect weekly_hours",
            "Cover all skills_to_develop",
            "No status words in title",
            "PROGRAM scope has no named assignees",
        ],
        personalization_points=["Use intern learning goals when present"],
        missing_context_notes=["Preferences unavailable"],
    )


class AIRoadmapTwoStepTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@ai.test",
            username="admin_ai",
            password="pass1234",
            full_name="Admin",
            role=Role.ADMIN,
            is_staff=True,
        )
        self.mentor = User.objects.create_user(
            email="mentor@ai.test",
            username="mentor_ai",
            password="pass1234",
            full_name="Mentor AI",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.mentor, department="Engineering", job_title="Lead"
        )
        self.other_mentor = User.objects.create_user(
            email="other@ai.test",
            username="other_ai",
            password="pass1234",
            full_name="Other Mentor",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.other_mentor, department="Design", job_title="Lead"
        )
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="AI Program",
            description="Build products",
            role="Software Intern",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 28),
            duration_weeks=4,
            department="Engineering",
            weekly_hours=20,
            maximum_interns=3,
            skills_needed=["Python"],
            skills_to_develop=["APIs", "Python Development", "AI Integrations"],
            goals="Ship features",
            expected_outcome="Independent contributor",
            final_project="Capstone app",
            additional_instructions="Focus on backend",
            status=ProgramStatus.ACTIVE,
        )
        self.intern_user = User.objects.create_user(
            email="intern@ai.test",
            username="intern_ai",
            password="pass1234",
            full_name="Intern AI",
            role=Role.INTERN,
        )
        self.intern = InternProfile.objects.create(
            user=self.intern_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn Django",
            major="CS",
            university="Test U",
        )
        InternSkill.objects.create(
            intern=self.intern, skill_name="Python", skill_level=2
        )
        InternSkill.objects.create(
            intern=self.intern, skill_name="APIs", skill_level=5
        )
        self.intern_user_b = User.objects.create_user(
            email="intern2@ai.test",
            username="intern2_ai",
            password="pass1234",
            full_name="Intern Two",
            role=Role.INTERN,
        )
        self.intern_b = InternProfile.objects.create(
            user=self.intern_user_b,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn React",
        )
        self.outside_intern_user = User.objects.create_user(
            email="outside@ai.test",
            username="outside_ai",
            password="pass1234",
            full_name="Outside Intern",
            role=Role.INTERN,
        )
        self.outside_intern = InternProfile.objects.create(
            user=self.outside_intern_user,
            mentor=self.other_mentor,
            learning_goals="Other",
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def _mock_prompt_only(self, mock_parse):
        prompt = build_prompt()

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedRoadmapPrompt:
                return prompt
            raise AssertionError("Call #2 must not run during prompt preview")

        mock_parse.side_effect = side_effect
        return prompt

    def _mock_full(self, mock_parse):
        prompt = build_prompt()
        roadmap = build_valid_roadmap(self.program)
        call_log = {"generator_payloads": []}

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedRoadmapPrompt:
                return prompt
            if text_format is GeneratedRoadmap:
                call_log["generator_payloads"].append(input_messages)
                return roadmap
            raise AssertionError(f"Unexpected schema {text_format}")

        mock_parse.side_effect = side_effect
        return prompt, roadmap, call_log

    def _build_prompt(self, **extra):
        payload = {
            "program_id": self.program.id,
            "assignment_scope": RoadmapScope.PROGRAM,
            "selected_intern_ids": [],
            **extra,
        }
        return self.client.post(PROMPT_URL, payload, format="json")

    @patch("services.ai.client.parse_structured")
    def test_step1_invokes_prompt_builder_only_and_returns_preview(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        self.auth(self.mentor)
        before = Roadmap.objects.count()
        response = self._build_prompt()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("preview_id", response.data)
        self.assertIn("final_roadmap_generation_prompt", response.data)
        self.assertEqual(response.data["prompt_title"], "Custom roadmap prompt")
        self.assertEqual(Roadmap.objects.count(), before)
        self.assertEqual(mock_parse.call_count, 1)
        self.assertIs(mock_parse.call_args.kwargs["text_format"], GeneratedRoadmapPrompt)

        final_prompt = response.data["final_roadmap_generation_prompt"]
        self.assertIn("Entire Program", final_prompt)
        self.assertIn("APIs", final_prompt)
        self.assertIn("Python Development", final_prompt)
        self.assertIn("AI Integrations", final_prompt)
        self.assertIn("Ship features", final_prompt)
        self.assertIn("Independent contributor", final_prompt)
        self.assertIn("Capstone app", final_prompt)
        self.assertIn("named leads", final_prompt.lower())
        self.assertIn("EVERY Program Skill to Develop", final_prompt)

    @patch("services.ai.client.parse_structured")
    def test_continue_uses_exact_final_prompt_and_creates_draft(self, mock_parse):
        _prompt, _roadmap, call_log = self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        preview_id = preview.data["preview_id"]
        final_prompt = preview.data["final_roadmap_generation_prompt"]
        self.assertEqual(Roadmap.objects.count(), 0)

        continue_response = self.client.post(
            CONTINUE_URL, {"preview_id": preview_id}, format="json"
        )
        self.assertEqual(continue_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(continue_response.data["generated_by_ai"])
        self.assertEqual(continue_response.data["status"], RoadmapStatus.DRAFT)
        self.assertEqual(continue_response.data["number_of_weeks"], 4)

        roadmap = Roadmap.objects.get(id=continue_response.data["id"])
        tasks = Task.objects.filter(roadmap_week__roadmap=roadmap)
        self.assertEqual(tasks.count(), 8)
        self.assertEqual(tasks.filter(source=TaskSource.AI_GENERATED).count(), 8)
        # PROGRAM scope assigns every current program intern to every task.
        self.assertEqual(
            TaskAssignment.objects.filter(task__in=tasks).count(),
            tasks.count() * 2,  # intern + intern_b
        )
        for task in tasks:
            self.assertEqual(
                set(task.assignments.values_list("intern_id", flat=True)),
                {self.intern.id, self.intern_b.id},
            )
        self.assertEqual(
            set(continue_response.data["weeks"][0]["tasks"][0]["assigned_intern_ids"]),
            {self.intern.id, self.intern_b.id},
        )

        # Prompt Builder once + Roadmap Generator once (success path)
        self.assertEqual(mock_parse.call_count, 2)
        generator_messages = call_log["generator_payloads"][0]
        import json

        user_payload = json.loads(generator_messages[1]["content"])
        self.assertEqual(
            user_payload["final_roadmap_generation_prompt"],
            final_prompt,
        )
        # Character-for-character reuse of the previewed Final Prompt.
        self.assertEqual(
            len(user_payload["final_roadmap_generation_prompt"]),
            len(final_prompt),
        )

    @patch("services.ai.client.parse_structured")
    def test_group_and_individual_continue_flow(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)

        group_preview = self._build_prompt(
            assignment_scope=RoadmapScope.GROUP,
            selected_intern_ids=[self.intern.id, self.intern_b.id],
        )
        self.assertEqual(group_preview.status_code, status.HTTP_200_OK)
        group = self.client.post(
            CONTINUE_URL,
            {"preview_id": group_preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(group.status_code, status.HTTP_201_CREATED)
        roadmap = Roadmap.objects.get(id=group.data["id"])
        self.assertEqual(
            set(roadmap.assigned_interns.values_list("id", flat=True)),
            {self.intern.id, self.intern_b.id},
        )

        individual_preview = self._build_prompt(
            assignment_scope=RoadmapScope.INDIVIDUAL,
            selected_intern_ids=[self.intern.id],
            mentor_focus_skills=["APIs", "Prompt Engineering"],
        )
        self.assertEqual(individual_preview.status_code, status.HTTP_200_OK)
        final_prompt = individual_preview.data["final_roadmap_generation_prompt"]
        self.assertIn("Intern AI", final_prompt)
        self.assertIn("Python: level 2 (Basic)", final_prompt)
        self.assertIn("APIs: level 5 (Expert)", final_prompt)
        self.assertIn("Prompt Engineering", final_prompt)
        self.assertIn("MENTOR-REQUESTED SKILLS TO FOCUS ON", final_prompt)
        self.assertEqual(
            individual_preview.data["mentor_focus_skills"],
            ["APIs", "Prompt Engineering"],
        )
        # Custom focus skill must not mutate Program.skills_to_develop
        self.program.refresh_from_db()
        self.assertNotIn("Prompt Engineering", self.program.skills_to_develop)

        individual = self.client.post(
            CONTINUE_URL,
            {"preview_id": individual_preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(individual.status_code, status.HTTP_201_CREATED)

    @patch("services.ai.client.parse_structured")
    def test_reference_txt_reaches_both_calls(self, mock_parse):
        _prompt, _roadmap, call_log = self._mock_full(mock_parse)
        reference_body = (
            "Django REST Framework must be used for all API endpoints.\n"
            "Acceptance: each endpoint needs authenticated JWT access.\n"
        )
        ProgramReferenceMaterial.objects.create(
            program=self.program,
            title="Technical Requirements",
            resource_type=ResourceType.DOC,
            file=SimpleUploadedFile(
                "technical_requirements.txt",
                reference_body.encode("utf-8"),
                content_type="text/plain",
            ),
        )
        self.auth(self.mentor)
        preview = self._build_prompt()
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        final_prompt = preview.data["final_roadmap_generation_prompt"]
        self.assertIn("Technical Requirements", final_prompt)
        self.assertIn("Django REST Framework must be used", final_prompt)
        self.assertIn("REFERENCE MATERIAL", final_prompt)

        # Call #1 received reference in user payload
        prompt_call = mock_parse.call_args_list[0]
        import json

        first_content = prompt_call.kwargs["input_messages"][1]["content"]
        self.assertIn("Django REST Framework must be used", first_content)
        self.assertIn("Technical Requirements", first_content)

        continue_response = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(continue_response.status_code, status.HTTP_201_CREATED)
        generator_payload = json.loads(call_log["generator_payloads"][0][1]["content"])
        self.assertEqual(
            generator_payload["final_roadmap_generation_prompt"], final_prompt
        )
        canon_refs = generator_payload["canonical_context"]["reference_materials"]
        self.assertTrue(canon_refs[0]["content_retrieved"])
        self.assertIn(
            "Django REST Framework must be used",
            canon_refs[0]["extracted_text"],
        )

    @patch("services.ai.client.parse_structured")
    def test_url_only_reference_is_not_marked_extracted(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        ProgramReferenceMaterial.objects.create(
            program=self.program,
            title="External Spec",
            resource_type=ResourceType.LINK,
            external_url="https://example.com/spec",
        )
        self.auth(self.mentor)
        preview = self._build_prompt()
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        notes = " ".join(preview.data["missing_context_notes"])
        self.assertIn("webpage content was not extracted", notes.lower())
        self.assertIn(
            "webpage content was not extracted",
            preview.data["final_roadmap_generation_prompt"].lower(),
        )

    @override_settings(OPENAI_REFERENCE_MAX_CHARS=50)
    @patch("services.ai.client.parse_structured")
    def test_oversized_reference_returns_clear_error(self, mock_parse):
        ProgramReferenceMaterial.objects.create(
            program=self.program,
            title="Huge Spec",
            resource_type=ResourceType.DOC,
            file=SimpleUploadedFile(
                "huge.txt",
                ("x" * 200).encode("utf-8"),
                content_type="text/plain",
            ),
        )
        self.auth(self.mentor)
        before = Roadmap.objects.count()
        preview = self._build_prompt()
        self.assertEqual(preview.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("too large", preview.data["detail"].lower())
        self.assertEqual(Roadmap.objects.count(), before)
        mock_parse.assert_not_called()

    def test_permissions_reject_other_roles_and_mentors(self):
        payload = {
            "program_id": self.program.id,
            "assignment_scope": RoadmapScope.PROGRAM,
            "selected_intern_ids": [],
        }
        self.auth(self.admin)
        self.assertEqual(
            self.client.post(PROMPT_URL, payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.auth(self.intern_user)
        self.assertEqual(
            self.client.post(PROMPT_URL, payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.auth(self.other_mentor)
        self.assertEqual(
            self.client.post(PROMPT_URL, payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_invalid_intern_selection_rejected(self):
        self.auth(self.mentor)
        response = self.client.post(
            PROMPT_URL,
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.GROUP,
                "selected_intern_ids": [self.outside_intern.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            PROMPT_URL,
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.INDIVIDUAL,
                "selected_intern_ids": [self.intern.id, self.intern_b.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("services.ai.client.parse_structured")
    def test_preview_ownership_and_expiry(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        preview_id = preview.data["preview_id"]

        self.auth(self.other_mentor)
        forbidden = self.client.post(
            CONTINUE_URL, {"preview_id": preview_id}, format="json"
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        cache.clear()
        self.auth(self.mentor)
        expired = self.client.post(
            CONTINUE_URL, {"preview_id": preview_id}, format="json"
        )
        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", expired.data["detail"].lower())

    @patch("services.ai.client.parse_structured")
    def test_prompt_builder_retries_once_then_fails(self, mock_parse):
        mock_parse.side_effect = [AIInvalidOutputError(), AIInvalidOutputError()]
        self.auth(self.mentor)
        before = Roadmap.objects.count()
        response = self._build_prompt()
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Roadmap.objects.count(), before)
        self.assertEqual(mock_parse.call_count, 2)

    @patch("services.ai.client.parse_structured")
    def test_roadmap_generator_retries_once_then_fails(self, mock_parse):
        prompt = build_prompt()

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedRoadmapPrompt:
                return prompt
            raise AIInvalidOutputError()

        mock_parse.side_effect = side_effect
        self.auth(self.mentor)
        preview = self._build_prompt()
        before = Roadmap.objects.count()
        response = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Roadmap.objects.count(), before)
        # 1 prompt + 2 generator attempts
        self.assertEqual(mock_parse.call_count, 3)

    @patch("services.ai.client.parse_structured")
    def test_persistence_failure_rolls_back(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        before_roadmaps = Roadmap.objects.count()
        before_weeks = RoadmapWeek.objects.count()
        before_tasks = Task.objects.count()
        with patch(
            "services.ai.persistence.Task.objects.create",
            side_effect=RuntimeError("db boom"),
        ):
            response = self.client.post(
                CONTINUE_URL,
                {"preview_id": preview.data["preview_id"]},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Roadmap.objects.count(), before_roadmaps)
        self.assertEqual(RoadmapWeek.objects.count(), before_weeks)
        self.assertEqual(Task.objects.count(), before_tasks)

    def test_validator_rejects_invalid_difficulty_requirement_weeks_and_dates(self):
        context = {
            "program": {
                "duration_weeks": 4,
                "start_date": self.program.start_date.isoformat(),
                "end_date": self.program.end_date.isoformat(),
            }
        }
        valid = build_valid_roadmap(self.program)
        bad_difficulty = valid.model_copy(deep=True)
        bad_difficulty.weeks[0].tasks[0].difficulty = "BEGINNER"  # type: ignore[assignment]
        with self.assertRaises(AIInvalidOutputError):
            validate_generated_roadmap(bad_difficulty, context=context)

        bad_requirement = build_valid_roadmap(self.program)
        bad_requirement.weeks[0].tasks[0].requirement_type = "MUST"  # type: ignore[assignment]
        with self.assertRaises(AIInvalidOutputError):
            validate_generated_roadmap(bad_requirement, context=context)

        bad_week = build_valid_roadmap(self.program)
        bad_week.weeks[0].week_number = 99
        with self.assertRaises(AIInvalidOutputError):
            validate_generated_roadmap(bad_week, context=context)

        bad_date = build_valid_roadmap(self.program)
        bad_date.weeks[0].tasks[0].due_date = "2020-01-01"
        with self.assertRaises(AIInvalidOutputError):
            validate_generated_roadmap(bad_date, context=context)

    def test_title_status_prefix_is_sanitized(self):
        from services.ai.validators import sanitize_roadmap_title

        self.assertEqual(
            sanitize_roadmap_title("DRAFT — PSUT Summer Internship Roadmap"),
            "PSUT Summer Internship Roadmap",
        )
        self.assertEqual(
            sanitize_roadmap_title("Published: AI Engineer Roadmap"),
            "AI Engineer Roadmap",
        )
        context = {
            "program": {
                "duration_weeks": 4,
                "start_date": self.program.start_date.isoformat(),
                "end_date": self.program.end_date.isoformat(),
            },
            "roadmap_scope": RoadmapScope.PROGRAM,
            "interns": [],
        }
        roadmap = build_valid_roadmap(self.program).model_copy(
            update={"title": "DRAFT — AI Program Roadmap"}
        )
        cleaned = validate_generated_roadmap(roadmap, context=context)
        self.assertEqual(cleaned.title, "AI Program Roadmap")
        self.assertNotIn("DRAFT", cleaned.title.upper())

    def test_program_scope_rejects_named_assignee_language(self):
        context = {
            "program": {
                "duration_weeks": 4,
                "start_date": self.program.start_date.isoformat(),
                "end_date": self.program.end_date.isoformat(),
            },
            "roadmap_scope": RoadmapScope.PROGRAM,
            "interns": [{"id": self.intern.id, "full_name": self.intern_user.full_name}],
        }
        roadmap = build_valid_roadmap(self.program).model_copy(deep=True)
        first_task = roadmap.weeks[0].tasks[0]
        roadmap.weeks[0].tasks[0] = first_task.model_copy(
            update={
                "description": (
                    f"Assignee: {self.intern_user.full_name} (lead) owns this deliverable."
                )
            }
        )
        with self.assertRaises(AIInvalidOutputError):
            validate_generated_roadmap(roadmap, context=context)

    def test_prompt_builder_system_mentions_program_scope_and_skills(self):
        from services.ai.prompt_builder import PROMPT_BUILDER_SYSTEM

        self.assertIn("skills_to_develop", PROMPT_BUILDER_SYSTEM)
        self.assertIn("PROGRAM", PROMPT_BUILDER_SYSTEM)
        self.assertIn("named individual interns", PROMPT_BUILDER_SYSTEM)
        self.assertIn("DRAFT", PROMPT_BUILDER_SYSTEM)
        self.assertIn("unsupported technologies", PROMPT_BUILDER_SYSTEM)

    def test_old_single_generate_endpoint_removed(self):
        self.auth(self.mentor)
        response = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.PROGRAM,
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            {status.HTTP_404_NOT_FOUND, status.HTTP_405_METHOD_NOT_ALLOWED},
        )

    def _continue_scope(self, *, scope, selected_intern_ids=None, mentor_focus_skills=None):
        preview = self._build_prompt(
            assignment_scope=scope,
            selected_intern_ids=selected_intern_ids or [],
            mentor_focus_skills=mentor_focus_skills or [],
        )
        self.assertEqual(preview.status_code, status.HTTP_200_OK)
        response = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response

    @patch("services.ai.client.parse_structured")
    def test_individual_tasks_assigned_only_to_selected_intern(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        response = self._continue_scope(
            scope=RoadmapScope.INDIVIDUAL,
            selected_intern_ids=[self.intern.id],
        )
        roadmap = Roadmap.objects.get(id=response.data["id"])
        self.assertEqual(roadmap.status, RoadmapStatus.DRAFT)
        tasks = Task.objects.filter(roadmap_week__roadmap=roadmap)
        self.assertTrue(tasks.exists())
        for task in tasks:
            assignee_ids = set(task.assignments.values_list("intern_id", flat=True))
            self.assertEqual(assignee_ids, {self.intern.id})
            self.assertNotIn(self.intern_b.id, assignee_ids)
        self.assertEqual(
            response.data["weeks"][0]["tasks"][0]["assigned_intern_ids"],
            [self.intern.id],
        )

    @patch("services.ai.client.parse_structured")
    def test_group_tasks_assigned_to_all_selected_interns(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        response = self._continue_scope(
            scope=RoadmapScope.GROUP,
            selected_intern_ids=[self.intern.id, self.intern_b.id],
        )
        roadmap = Roadmap.objects.get(id=response.data["id"])
        tasks = Task.objects.filter(roadmap_week__roadmap=roadmap)
        for task in tasks:
            self.assertEqual(
                set(task.assignments.values_list("intern_id", flat=True)),
                {self.intern.id, self.intern_b.id},
            )

    @patch("services.ai.client.parse_structured")
    def test_program_tasks_assigned_to_all_program_interns(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        response = self._continue_scope(scope=RoadmapScope.PROGRAM)
        roadmap = Roadmap.objects.get(id=response.data["id"])
        self.assertEqual(
            set(roadmap.assigned_interns.values_list("id", flat=True)),
            {self.intern.id, self.intern_b.id},
        )
        tasks = Task.objects.filter(roadmap_week__roadmap=roadmap)
        for task in tasks:
            self.assertEqual(
                set(task.assignments.values_list("intern_id", flat=True)),
                {self.intern.id, self.intern_b.id},
            )

    @patch("services.ai.client.parse_structured")
    def test_draft_assignments_hidden_from_intern_until_publish(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        response = self._continue_scope(
            scope=RoadmapScope.INDIVIDUAL,
            selected_intern_ids=[self.intern.id],
        )
        roadmap = Roadmap.objects.get(id=response.data["id"])
        assignment_ids = list(
            TaskAssignment.objects.filter(
                task__roadmap_week__roadmap=roadmap,
                intern=self.intern,
            ).values_list("id", flat=True)
        )
        self.assertTrue(assignment_ids)

        self.auth(self.intern_user)
        listed = self.client.get("/api/tasks/assignments/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        listed_rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        visible_ids = {item["id"] for item in listed_rows}
        self.assertTrue(set(assignment_ids).isdisjoint(visible_ids))
        blocked = self.client.get(f"/api/tasks/assignments/{assignment_ids[0]}/")
        self.assertEqual(blocked.status_code, status.HTTP_404_NOT_FOUND)

        self.auth(self.mentor)
        published = self.client.post(f"/api/roadmaps/{roadmap.id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertEqual(published.data["status"], RoadmapStatus.PUBLISHED)

        self.auth(self.intern_user)
        listed_after = self.client.get("/api/tasks/assignments/")
        self.assertEqual(listed_after.status_code, status.HTTP_200_OK)
        listed_after_rows = (
            listed_after.data["results"]
            if isinstance(listed_after.data, dict)
            else listed_after.data
        )
        visible_after = {item["id"] for item in listed_after_rows}
        self.assertTrue(set(assignment_ids).issubset(visible_after))

    @patch("services.ai.client.parse_structured")
    def test_publish_does_not_duplicate_existing_assignments(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        response = self._continue_scope(
            scope=RoadmapScope.GROUP,
            selected_intern_ids=[self.intern.id, self.intern_b.id],
        )
        roadmap = Roadmap.objects.get(id=response.data["id"])
        before = TaskAssignment.objects.filter(
            task__roadmap_week__roadmap=roadmap
        ).count()
        self.assertGreater(before, 0)

        published = self.client.post(f"/api/roadmaps/{roadmap.id}/publish/", {}, format="json")
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        after = TaskAssignment.objects.filter(
            task__roadmap_week__roadmap=roadmap
        ).count()
        self.assertEqual(after, before)

    @patch("services.ai.client.parse_structured")
    def test_mentor_can_edit_task_assignees_before_publish(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        response = self._continue_scope(
            scope=RoadmapScope.GROUP,
            selected_intern_ids=[self.intern.id, self.intern_b.id],
        )
        task_id = response.data["weeks"][0]["tasks"][0]["id"]
        updated = self.client.patch(
            f"/api/tasks/{task_id}/",
            {"assign_intern_ids": [self.intern.id]},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data["assigned_intern_ids"], [self.intern.id])
        task = Task.objects.get(id=task_id)
        self.assertEqual(
            set(task.assignments.values_list("intern_id", flat=True)),
            {self.intern.id},
        )

        published = self.client.post(
            f"/api/roadmaps/{response.data['id']}/publish/",
            {},
            format="json",
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        task.refresh_from_db()
        # Publish must not re-add the removed intern.
        self.assertEqual(
            set(task.assignments.values_list("intern_id", flat=True)),
            {self.intern.id},
        )

    def test_manual_task_assignment_still_works(self):
        self.auth(self.mentor)
        roadmap = Roadmap.objects.create(
            program=self.program,
            title="Manual roadmap",
            summary="Manual",
            assignment_scope=RoadmapScope.INDIVIDUAL,
            number_of_weeks=1,
            status=RoadmapStatus.DRAFT,
        )
        roadmap.assigned_interns.set([self.intern])
        week = RoadmapWeek.objects.create(
            roadmap=roadmap,
            week_number=1,
            weekly_focus="Focus",
            display_order=1,
        )
        created = self.client.post(
            "/api/tasks/",
            {
                "program": self.program.id,
                "roadmap_week": week.id,
                "title": "Manual task",
                "description": "Do the work",
                "difficulty": "EASY",
                "estimated_time_minutes": 60,
                "due_date": self.program.start_date.isoformat(),
                "requirement_type": "REQUIRED",
                "source": "MANUAL",
                "assign_intern_ids": [self.intern.id],
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["assigned_intern_ids"], [self.intern.id])
        self.assertEqual(
            TaskAssignment.objects.filter(task_id=created.data["id"]).count(),
            1,
        )


class RoadmapValidationDiagnosticsTests(TestCase):
    """Expose real invalid_output causes via development logs (no rule changes)."""

    def setUp(self):
        self.client = APIClient()
        self.mentor = User.objects.create_user(
            email="mentor-diag@ai.test",
            username="mentor_diag",
            password="pass1234",
            full_name="Mentor Diag",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(user=self.mentor, department="Eng", job_title="Lead")
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="Diag Program",
            description="Desc",
            role="Intern",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 28),
            duration_weeks=4,
            department="Engineering",
            weekly_hours=20,
            maximum_interns=3,
            goals="Ship",
            skills_to_develop=["APIs"],
            expected_outcome="Ready",
            final_project="Capstone",
            status=ProgramStatus.ACTIVE,
        )

    def _context(self):
        return {
            "program": {
                "id": self.program.id,
                "duration_weeks": self.program.duration_weeks,
                "start_date": self.program.start_date.isoformat(),
                "end_date": self.program.end_date.isoformat(),
            }
        }

    def test_invalid_week_count_logs_useful_reason(self):
        roadmap = build_valid_roadmap(self.program)
        roadmap = roadmap.model_copy(
            update={
                "number_of_weeks": 4,
                "weeks": roadmap.weeks[:3],
            }
        )
        with self.assertLogs("ai.generation", level="WARNING") as cm:
            with self.assertRaises(AIInvalidOutputError) as raised:
                validate_generated_roadmap(roadmap, context=self._context())
        self.assertEqual(
            raised.exception.user_message,
            "AI roadmap generation could not produce a valid roadmap. Please try again.",
        )
        self.assertEqual(raised.exception.reason, "Expected exactly 4 weeks")
        self.assertEqual(raised.exception.expected, 4)
        self.assertEqual(raised.exception.received, 3)
        joined = "\n".join(cm.output)
        self.assertIn("ROADMAP_VALIDATION_FAILED", joined)
        self.assertIn("Expected exactly 4 weeks", joined)
        self.assertIn("Expected: 4", joined)
        self.assertIn("Received: 3", joined)
        self.assertNotIn("sk-", joined)
        self.assertNotIn("api_key", joined.lower())

    def test_invalid_task_due_date_logs_useful_reason(self):
        from services.ai.validators import week_boundaries

        roadmap = build_valid_roadmap(self.program)
        week_start, week_end = week_boundaries(
            self.program.start_date,
            self.program.end_date,
            1,
            self.program.duration_weeks,
        )
        bad_due = (week_end + timedelta(days=1)).isoformat()
        roadmap.weeks[0].tasks[0].due_date = bad_due
        with self.assertLogs("ai.generation", level="WARNING") as cm:
            with self.assertRaises(AIInvalidOutputError) as raised:
                validate_generated_roadmap(roadmap, context=self._context())
        self.assertEqual(raised.exception.reason, "Task due date outside week range")
        self.assertEqual(raised.exception.path, "weeks[0].tasks[0].due_date")
        self.assertIn(week_start.isoformat(), str(raised.exception.expected))
        self.assertIn(week_end.isoformat(), str(raised.exception.expected))
        self.assertEqual(raised.exception.received, bad_due)
        joined = "\n".join(cm.output)
        self.assertIn("ROADMAP_VALIDATION_FAILED", joined)
        self.assertIn("Task due date outside week range", joined)
        self.assertIn("weeks[0].tasks[0].due_date", joined)

    def test_missing_required_generated_field_logs_useful_reason(self):
        from pydantic import ValidationError

        from services.ai.client import _invalid_from_validation_error
        from services.ai.schemas import GeneratedRoadmap

        with self.assertRaises(ValidationError) as pydantic_exc:
            GeneratedRoadmap.model_validate(
                {
                    "title": "Incomplete",
                    "summary": "Missing weeks",
                    "number_of_weeks": 4,
                }
            )
        with self.assertLogs("ai.generation", level="WARNING") as cm:
            err = _invalid_from_validation_error(
                pydantic_exc.exception,
                text_format=GeneratedRoadmap,
            )
        self.assertIsInstance(err, AIInvalidOutputError)
        self.assertEqual(
            err.user_message,
            "AI roadmap generation could not produce a valid roadmap. Please try again.",
        )
        joined = "\n".join(cm.output)
        self.assertIn("ROADMAP_STRUCTURED_OUTPUT_FAILED", joined)
        self.assertTrue(err.path == "weeks" or "weeks" in (err.reason or ""))
        self.assertNotIn("OPENAI_API_KEY", joined)
        self.assertNotIn("Bearer ", joined)

    @patch("services.ai.client.parse_structured")
    def test_retry_attempts_are_distinguishable_in_logs(self, mock_parse):
        prompt = build_prompt()

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedRoadmapPrompt:
                return prompt
            raise AIInvalidOutputError(
                reason="Forced invalid output for retry logging",
                path="weeks",
                expected=4,
                received=2,
            )

        mock_parse.side_effect = side_effect
        self.client.force_authenticate(user=self.mentor)
        with self.assertLogs("ai.generation", level="WARNING") as cm:
            preview = self.client.post(
                PROMPT_URL,
                {
                    "program_id": self.program.id,
                    "assignment_scope": "PROGRAM",
                    "selected_intern_ids": [],
                },
                format="json",
            )
            self.assertEqual(preview.status_code, status.HTTP_200_OK)
            response = self.client.post(
                CONTINUE_URL,
                {"preview_id": preview.data["preview_id"]},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(
            response.data["detail"],
            "AI roadmap generation could not produce a valid roadmap. Please try again.",
        )
        joined = "\n".join(cm.output)
        self.assertIn("ROADMAP_GENERATION_ATTEMPT_1_FAILED", joined)
        self.assertIn("ROADMAP_GENERATION_RETRY_STARTED", joined)
        self.assertIn("ROADMAP_GENERATION_ATTEMPT_2_FAILED", joined)
        self.assertIn("Forced invalid output for retry logging", joined)
        self.assertNotIn("sk-", joined)

    def test_valid_roadmap_behavior_unchanged(self):
        roadmap = build_valid_roadmap(self.program)
        cleaned = validate_generated_roadmap(roadmap, context=self._context())
        self.assertEqual(cleaned.number_of_weeks, 4)
        self.assertEqual(len(cleaned.weeks), 4)
        self.assertTrue(cleaned.title)


class RoadmapWeekBoundaryTests(TestCase):
    """Canonical 7-day week boundaries shared by prompt + validator."""

    PROGRAM_START = date(2026, 7, 22)
    PROGRAM_END = date(2026, 9, 1)
    DURATION_WEEKS = 6

    EXPECTED = {
        1: (date(2026, 7, 22), date(2026, 7, 28)),
        2: (date(2026, 7, 29), date(2026, 8, 4)),
        3: (date(2026, 8, 5), date(2026, 8, 11)),
        4: (date(2026, 8, 12), date(2026, 8, 18)),
        5: (date(2026, 8, 19), date(2026, 8, 25)),
        6: (date(2026, 8, 26), date(2026, 9, 1)),
    }

    def setUp(self):
        self.mentor = User.objects.create_user(
            email="mentor-weeks@ai.test",
            username="mentor_weeks",
            password="pass1234",
            full_name="Mentor Weeks",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(user=self.mentor, department="Eng", job_title="Lead")
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="AI Internship Management Platform Development",
            description="Build an AI internship platform",
            role="AI / Full-Stack Software Engineering Intern",
            start_date=self.PROGRAM_START,
            end_date=self.PROGRAM_END,
            duration_weeks=self.DURATION_WEEKS,
            department="Artificial Intelligence",
            weekly_hours=40,
            maximum_interns=5,
            goals="Deliver MVP",
            skills_to_develop=["APIs", "Testing"],
            expected_outcome="Working platform",
            final_project="Capstone",
            status=ProgramStatus.ACTIVE,
        )

    def _context(self):
        return {
            "program": {
                "id": self.program.id,
                "title": self.program.title,
                "description": self.program.description,
                "role": self.program.role,
                "department": self.program.department,
                "start_date": self.program.start_date.isoformat(),
                "end_date": self.program.end_date.isoformat(),
                "duration_weeks": self.program.duration_weeks,
                "weekly_hours": self.program.weekly_hours,
                "maximum_interns": self.program.maximum_interns,
                "goals": self.program.goals,
                "skills_needed": [],
                "skills_to_develop": self.program.skills_to_develop,
                "expected_outcome": self.program.expected_outcome,
                "final_project": self.program.final_project,
                "additional_instructions": "",
                "mentor": {"full_name": self.mentor.full_name},
            },
            "roadmap_scope": "PROGRAM",
            "interns": [],
            "reference_materials": [],
            "mentor_focus_skills": [],
            "unavailable_data": [],
        }

    def test_exact_six_week_boundaries_for_program(self):
        from services.ai.roadmap_week_dates import week_boundaries
        from services.ai.validators import week_boundaries as validator_week_boundaries

        self.assertEqual(self.program.duration_weeks, 6)
        self.assertEqual(self.program.start_date, self.PROGRAM_START)
        self.assertEqual(self.program.end_date, self.PROGRAM_END)

        for week_number, (expected_start, expected_end) in self.EXPECTED.items():
            canonical = week_boundaries(
                self.PROGRAM_START, self.PROGRAM_END, week_number, self.DURATION_WEEKS
            )
            validated = validator_week_boundaries(
                self.PROGRAM_START, self.PROGRAM_END, week_number, self.DURATION_WEEKS
            )
            self.assertEqual(canonical, (expected_start, expected_end))
            self.assertEqual(validated, canonical)

        self.assertEqual(self.EXPECTED[1][0], date(2026, 7, 22))
        self.assertEqual(self.EXPECTED[1][1], date(2026, 7, 28))
        self.assertEqual(self.EXPECTED[2][0], date(2026, 7, 29))
        self.assertEqual(self.EXPECTED[6], (date(2026, 8, 26), date(2026, 9, 1)))

    def test_weeks_have_no_gaps_or_overlaps(self):
        from services.ai.roadmap_week_dates import iter_program_week_boundaries

        rows = iter_program_week_boundaries(
            self.PROGRAM_START, self.PROGRAM_END, self.DURATION_WEEKS
        )
        self.assertEqual(len(rows), 6)
        for index in range(len(rows) - 1):
            _, _start, end = rows[index]
            _, next_start, _next_end = rows[index + 1]
            self.assertEqual(next_start, end + timedelta(days=1))
            self.assertLess(end, next_start)

    def test_jul_28_due_date_is_valid_for_week_1_jul_29_is_not(self):
        """Regression: the Continue failure that rejected 2026-07-28 for Week 1."""
        roadmap = build_valid_roadmap(self.program)
        self.assertEqual(len(roadmap.weeks), 6)
        # Exact failing case from production logs: Week 1 task due on Jul 28.
        roadmap.weeks[0].tasks[0].due_date = "2026-07-28"

        # Last day of Week 1 must validate.
        cleaned = validate_generated_roadmap(roadmap, context=self._context())
        self.assertEqual(cleaned.number_of_weeks, 6)
        self.assertEqual(len(cleaned.weeks), 6)
        self.assertEqual(cleaned.weeks[0].tasks[0].due_date, "2026-07-28")

        # Day after Week 1 must fail for Week 1.
        bad = build_valid_roadmap(self.program)
        bad.weeks[0].tasks[0].due_date = "2026-07-29"
        with self.assertRaises(AIInvalidOutputError) as raised:
            validate_generated_roadmap(bad, context=self._context())
        self.assertEqual(raised.exception.reason, "Task due date outside week range")
        self.assertEqual(raised.exception.path, "weeks[0].tasks[0].due_date")
        self.assertEqual(raised.exception.received, "2026-07-29")
        self.assertIn("2026-07-22", str(raised.exception.expected))
        self.assertIn("2026-07-28", str(raised.exception.expected))

    def test_due_date_on_first_and_last_day_of_week_are_valid(self):
        roadmap = build_valid_roadmap(self.program)
        roadmap.weeks[1].tasks[0].due_date = "2026-07-29"  # Week 2 start
        roadmap.weeks[1].tasks[1].due_date = "2026-08-04"  # Week 2 end
        cleaned = validate_generated_roadmap(roadmap, context=self._context())
        self.assertEqual(cleaned.weeks[1].tasks[0].due_date, "2026-07-29")
        self.assertEqual(cleaned.weeks[1].tasks[1].due_date, "2026-08-04")

    def test_final_week_never_exceeds_program_end(self):
        from services.ai.roadmap_week_dates import week_boundaries

        start, end = week_boundaries(
            self.PROGRAM_START, self.PROGRAM_END, 6, self.DURATION_WEEKS
        )
        self.assertEqual(end, self.PROGRAM_END)
        self.assertLessEqual(end, self.PROGRAM_END)
        self.assertEqual(start, date(2026, 8, 26))

    def test_prompt_uses_same_boundaries_as_validator(self):
        from services.ai.final_prompt import build_final_roadmap_generation_prompt
        from services.ai.roadmap_week_dates import week_boundaries
        from services.ai.validators import week_boundaries as validator_week_boundaries

        prompt_text = build_final_roadmap_generation_prompt(
            context=self._context(),
            prompt_builder_result=build_prompt(),
        )
        self.assertIn("AUTHORITATIVE ROADMAP WEEK BOUNDARIES", prompt_text)
        for week_number in range(1, 7):
            canonical = week_boundaries(
                self.PROGRAM_START, self.PROGRAM_END, week_number, self.DURATION_WEEKS
            )
            validated = validator_week_boundaries(
                self.PROGRAM_START, self.PROGRAM_END, week_number, self.DURATION_WEEKS
            )
            self.assertEqual(canonical, validated)
            line = (
                f"Week {week_number}: {canonical[0].isoformat()} → "
                f"{canonical[1].isoformat()}"
            )
            self.assertIn(line, prompt_text)

    def test_existing_valid_roadmap_generation_still_works(self):
        roadmap = build_valid_roadmap(self.program)
        cleaned = validate_generated_roadmap(roadmap, context=self._context())
        self.assertEqual(cleaned.number_of_weeks, 6)
        self.assertEqual(len(cleaned.weeks), 6)
        self.assertTrue(cleaned.title)
