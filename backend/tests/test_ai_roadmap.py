"""AI roadmap generation tests — OpenAI is fully mocked (no real API calls)."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MentorProfile, User
from apps.programs.models import InternProfile, InternshipProgram
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.tasks.models import Task, TaskAssignment
from common.constants import ProgramStatus, Role, RoadmapScope, RoadmapStatus, TaskSource
from services.ai.exceptions import AIInvalidOutputError
from services.ai.schemas import (
    GeneratedRoadmap,
    GeneratedRoadmapPrompt,
    GeneratedTask,
    GeneratedWeek,
)
from services.ai.validators import validate_generated_roadmap


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
    weeks = [
        _week_payload(
            week_number,
            program.start_date + timedelta(days=(week_number - 1) * 7),
            min(program.start_date + timedelta(days=week_number * 7 - 1), program.end_date),
        )
        for week_number in range(1, program.duration_weeks + 1)
    ]
    # Align due dates with validator week windows by re-validating through helper
    from services.ai.validators import week_boundaries

    aligned = []
    for week in weeks:
        start, end = week_boundaries(
            program.start_date,
            program.end_date,
            week.week_number,
            program.duration_weeks,
        )
        aligned.append(
            _week_payload(week.week_number, start, end, tasks=2),
        )
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
            "Do not put DRAFT in the title."
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


class AIRoadmapGenerationTests(TestCase):
    def setUp(self):
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
            skills_to_develop=["APIs"],
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

    def _mock_success(self, mock_parse):
        prompt = build_prompt()
        roadmap = build_valid_roadmap(self.program)

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedRoadmapPrompt:
                return prompt
            if text_format is GeneratedRoadmap:
                return roadmap
            raise AssertionError(f"Unexpected schema {text_format}")

        mock_parse.side_effect = side_effect

    @patch("services.ai.client.parse_structured")
    def test_owning_mentor_can_generate_program_scope(self, mock_parse):
        self._mock_success(mock_parse)
        self.auth(self.mentor)
        response = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.PROGRAM,
                "selected_intern_ids": [],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["generated_by_ai"])
        self.assertEqual(response.data["status"], RoadmapStatus.DRAFT)
        self.assertEqual(response.data["number_of_weeks"], 4)
        self.assertEqual(len(response.data["weeks"]), 4)
        roadmap = Roadmap.objects.get(id=response.data["id"])
        self.assertEqual(roadmap.weeks.count(), 4)
        tasks = Task.objects.filter(roadmap_week__roadmap=roadmap)
        self.assertEqual(tasks.count(), 8)
        self.assertTrue(tasks.filter(source=TaskSource.AI_GENERATED).count() == 8)
        self.assertEqual(TaskAssignment.objects.filter(task__in=tasks).count(), 0)
        self.assertGreaterEqual(mock_parse.call_count, 2)

    @patch("services.ai.client.parse_structured")
    def test_group_and_individual_scopes(self, mock_parse):
        self._mock_success(mock_parse)
        self.auth(self.mentor)

        group = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.GROUP,
                "selected_intern_ids": [self.intern.id, self.intern_b.id],
            },
            format="json",
        )
        self.assertEqual(group.status_code, status.HTTP_201_CREATED)
        roadmap = Roadmap.objects.get(id=group.data["id"])
        self.assertEqual(set(roadmap.assigned_interns.values_list("id", flat=True)), {
            self.intern.id,
            self.intern_b.id,
        })

        individual = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.INDIVIDUAL,
                "selected_intern_ids": [self.intern.id],
            },
            format="json",
        )
        self.assertEqual(individual.status_code, status.HTTP_201_CREATED)

    def test_permissions_reject_other_roles_and_mentors(self):
        payload = {
            "program_id": self.program.id,
            "assignment_scope": RoadmapScope.PROGRAM,
            "selected_intern_ids": [],
        }
        self.auth(self.admin)
        self.assertEqual(
            self.client.post("/api/roadmaps/generate/", payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.auth(self.intern_user)
        self.assertEqual(
            self.client.post("/api/roadmaps/generate/", payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.auth(self.other_mentor)
        self.assertEqual(
            self.client.post("/api/roadmaps/generate/", payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_invalid_intern_selection_rejected(self):
        self.auth(self.mentor)
        response = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.GROUP,
                "selected_intern_ids": [self.outside_intern.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.INDIVIDUAL,
                "selected_intern_ids": [self.intern.id, self.intern_b.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("services.ai.client.parse_structured")
    def test_prompt_builder_retries_once_then_fails(self, mock_parse):
        mock_parse.side_effect = [
            AIInvalidOutputError(),
            AIInvalidOutputError(),
        ]
        self.auth(self.mentor)
        before = Roadmap.objects.count()
        response = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.PROGRAM,
            },
            format="json",
        )
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
        before = Roadmap.objects.count()
        response = self.client.post(
            "/api/roadmaps/generate/",
            {
                "program_id": self.program.id,
                "assignment_scope": RoadmapScope.PROGRAM,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(Roadmap.objects.count(), before)
        # 1 prompt + 2 generator attempts
        self.assertEqual(mock_parse.call_count, 3)

    @patch("services.ai.client.parse_structured")
    def test_persistence_failure_rolls_back(self, mock_parse):
        self._mock_success(mock_parse)
        self.auth(self.mentor)
        before_roadmaps = Roadmap.objects.count()
        before_weeks = RoadmapWeek.objects.count()
        before_tasks = Task.objects.count()
        with patch(
            "services.ai.persistence.Task.objects.create",
            side_effect=RuntimeError("db boom"),
        ):
            response = self.client.post(
                "/api/roadmaps/generate/",
                {
                    "program_id": self.program.id,
                    "assignment_scope": RoadmapScope.PROGRAM,
                },
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
