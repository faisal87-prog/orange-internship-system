"""AI weekly report two-step generation tests — OpenAI fully mocked."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MentorProfile, User
from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import WeeklyReport
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.submissions.models import Submission
from apps.tasks.models import Task, TaskAssignment
from common.constants import (
    AiContentStatus,
    ProgramStatus,
    RequirementType,
    Role,
    RoadmapScope,
    RoadmapStatus,
    TaskAssignmentStatus,
    TaskDifficulty,
    TaskSource,
)
from services.ai.schemas import GeneratedWeeklyReport, GeneratedWeeklyReportPrompt
from services.weekly_score import calculate_overall_weekly_score

PROMPT_URL = "/api/reports/weekly/generate/prompt/"
CONTINUE_URL = "/api/reports/weekly/generate/continue/"


def build_prompt() -> GeneratedWeeklyReportPrompt:
    return GeneratedWeeklyReportPrompt(
        prompt_title="Week performance prompt",
        weekly_report_generation_prompt=(
            "Write an evidence-based weekly report for the selected intern and week. "
            "Do not invent scores or achievements."
        ),
        important_constraints=["Use supplied evidence only", "Do not invent scores"],
        personalization_points=["Use learning goals when present"],
        missing_context_notes=["Preferences unavailable"],
    )


def build_report() -> GeneratedWeeklyReport:
    return GeneratedWeeklyReport(
        performance_summary="The intern completed key required work with solid quality.",
        achievements="Finished the API task\nAddressed mentor revision feedback",
        learning_progress="Demonstrated progress against weekly learning objectives.",
        productivity_analysis="Submitted on time for scored tasks and revised when asked.",
        mentor_focus_suggestions="Review remaining optional work\nCoach revision responses",
        recommended_next_focus="Continue API practice and reinforce testing habits next week.",
    )


class AIWeeklyReportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@wr.test",
            username="admin_wr",
            password="pass1234",
            full_name="Admin",
            role=Role.ADMIN,
            is_staff=True,
        )
        self.mentor = User.objects.create_user(
            email="mentor@wr.test",
            username="mentor_wr",
            password="pass1234",
            full_name="Mentor WR",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(user=self.mentor, department="Eng", job_title="Lead")
        self.other_mentor = User.objects.create_user(
            email="other@wr.test",
            username="other_wr",
            password="pass1234",
            full_name="Other Mentor",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(user=self.other_mentor, department="Design", job_title="Lead")
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="WR Program",
            description="Desc",
            role="Intern",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 28),
            duration_weeks=4,
            department="Engineering",
            weekly_hours=20,
            maximum_interns=3,
            goals="Ship features",
            skills_to_develop=["APIs"],
            expected_outcome="Independent contributor",
            final_project="Capstone",
            status=ProgramStatus.ACTIVE,
        )
        self.intern_user = User.objects.create_user(
            email="intern@wr.test",
            username="intern_wr",
            password="pass1234",
            full_name="Intern WR",
            role=Role.INTERN,
        )
        self.intern = InternProfile.objects.create(
            user=self.intern_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn APIs",
        )
        self.intern_b_user = User.objects.create_user(
            email="internb@wr.test",
            username="internb_wr",
            password="pass1234",
            full_name="Intern B",
            role=Role.INTERN,
        )
        self.intern_b = InternProfile.objects.create(
            user=self.intern_b_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn UI",
        )
        self.roadmap = Roadmap.objects.create(
            program=self.program,
            title="Published Roadmap",
            summary="Summary",
            assignment_scope=RoadmapScope.PROGRAM,
            number_of_weeks=1,
            status=RoadmapStatus.PUBLISHED,
        )
        self.week = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=1,
            weekly_focus="APIs",
            learning_objectives=["Build endpoints"],
            expected_skills_gained=["REST"],
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            display_order=1,
        )
        self.task = Task.objects.create(
            roadmap_week=self.week,
            program=self.program,
            created_by=self.mentor,
            title="API Task",
            description="Build endpoint",
            difficulty=TaskDifficulty.MEDIUM,
            estimated_time_minutes=120,
            due_date=date(2026, 6, 5),
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
            deliverable="PR",
            success_criteria="Tests pass",
        )
        self.assignment = TaskAssignment.objects.create(
            task=self.task,
            intern=self.intern,
            status=TaskAssignmentStatus.COMPLETED,
            score=80,
            mentor_feedback="Good work",
        )
        TaskAssignment.objects.create(
            task=self.task,
            intern=self.intern_b,
            status=TaskAssignmentStatus.TO_DO,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def _mock_prompt_only(self, mock_parse):
        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedWeeklyReportPrompt:
                return build_prompt()
            raise AssertionError("Call #2 must not run during prompt preview")

        mock_parse.side_effect = side_effect

    def _mock_full(self, mock_parse):
        call_log = {"generator_payloads": []}

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedWeeklyReportPrompt:
                return build_prompt()
            if text_format is GeneratedWeeklyReport:
                call_log["generator_payloads"].append(input_messages)
                return build_report()
            raise AssertionError(f"Unexpected schema {text_format}")

        mock_parse.side_effect = side_effect
        return call_log

    def _build_prompt(self, **extra):
        payload = {
            "program_id": self.program.id,
            "intern_id": self.intern.id,
            "roadmap_week_id": self.week.id,
            **extra,
        }
        return self.client.post(PROMPT_URL, payload, format="json")

    def test_score_averages_only_scored_tasks(self):
        needs_revision_task = Task.objects.create(
            roadmap_week=self.week,
            program=self.program,
            created_by=self.mentor,
            title="Revision Task",
            description="Revise",
            difficulty=TaskDifficulty.EASY,
            estimated_time_minutes=30,
            due_date=date(2026, 6, 6),
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
        )
        TaskAssignment.objects.create(
            task=needs_revision_task,
            intern=self.intern,
            status=TaskAssignmentStatus.NEEDS_REVISION,
            score=None,
            mentor_feedback="Please revise",
        )
        second = Task.objects.create(
            roadmap_week=self.week,
            program=self.program,
            created_by=self.mentor,
            title="Second",
            description="More",
            difficulty=TaskDifficulty.EASY,
            estimated_time_minutes=30,
            due_date=date(2026, 6, 6),
            requirement_type=RequirementType.OPTIONAL,
            source=TaskSource.MANUAL,
        )
        TaskAssignment.objects.create(
            task=second,
            intern=self.intern,
            status=TaskAssignmentStatus.COMPLETED,
            score=90,
        )
        self.assertEqual(calculate_overall_weekly_score(self.intern, self.week), 85)
        empty = calculate_overall_weekly_score(self.intern_b, self.week)
        self.assertIsNone(empty)

    @patch("services.ai.client.parse_structured")
    def test_step1_prompt_only_and_context_is_intern_scoped(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        self.auth(self.mentor)
        before = WeeklyReport.objects.count()
        response = self._build_prompt()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("preview_id", response.data)
        self.assertEqual(WeeklyReport.objects.count(), before)
        self.assertEqual(mock_parse.call_count, 1)
        self.assertIs(
            mock_parse.call_args.kwargs["text_format"],
            GeneratedWeeklyReportPrompt,
        )
        content = mock_parse.call_args.kwargs["input_messages"][1]["content"]
        self.assertIn("Intern WR", content)
        self.assertIn("API Task", content)
        self.assertNotIn("Intern B private", content)
        final_prompt = response.data["final_weekly_report_generation_prompt"]
        self.assertIn("OVERALL WEEKLY SCORE", final_prompt)
        self.assertIn("80 / 100", final_prompt)

    @patch("services.ai.client.parse_structured")
    def test_continue_uses_exact_prompt_and_creates_draft(self, mock_parse):
        call_log = self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        final_prompt = preview.data["final_weekly_report_generation_prompt"]
        response = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], AiContentStatus.DRAFT)
        self.assertTrue(response.data["generated_by_ai"])
        self.assertEqual(response.data["overall_weekly_score"], 80)
        self.assertEqual(response.data["additional_mentor_notes"], "")
        import json

        payload = json.loads(call_log["generator_payloads"][0][1]["content"])
        self.assertEqual(
            payload["final_weekly_report_generation_prompt"],
            final_prompt,
        )

        self.auth(self.intern_user)
        listed = self.client.get("/api/reports/weekly/")
        rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        self.assertEqual(rows, [])

    @patch("services.ai.client.parse_structured")
    def test_permissions(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        payload = {
            "program_id": self.program.id,
            "intern_id": self.intern.id,
            "roadmap_week_id": self.week.id,
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

    @patch("services.ai.client.parse_structured")
    def test_approve_visibility_and_pdf(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        created = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        report_id = created.data["id"]
        patched = self.client.patch(
            f"/api/reports/weekly/{report_id}/",
            {"additional_mentor_notes": "Keep up the pace."},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        approved = self.client.post(f"/api/reports/weekly/{report_id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(approved.data["status"], AiContentStatus.APPROVED)
        self.assertTrue(approved.data["pdf_url"])

        self.auth(self.intern_user)
        listed = self.client.get("/api/reports/weekly/")
        rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        self.assertEqual(len(rows), 1)
        pdf = self.client.get(f"/api/reports/weekly/{report_id}/download_pdf/")
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        report = WeeklyReport.objects.get(id=report_id)
        self.assertTrue(
            Path(report.pdf_file.name).name.startswith("week-1-report-intern-wr")
        )
        disposition = pdf.get("Content-Disposition", "")
        self.assertIn("week-1-report-intern-wr.pdf", disposition)

    def test_weekly_report_pdf_title_and_filename_helpers(self):
        from services.pdf import weekly_report_pdf_filename, weekly_report_title

        report = WeeklyReport(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.week,
        )
        self.assertEqual(weekly_report_title(report), "Week 1 Report for Intern WR")
        self.assertEqual(
            weekly_report_pdf_filename(report),
            "week-1-report-intern-wr.pdf",
        )

    @patch("services.ai.client.parse_structured")
    def test_empty_week_null_score_and_no_fabricated_score(self, mock_parse):
        TaskAssignment.objects.filter(intern=self.intern).update(score=None)
        call_log = self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        self.assertIsNone(preview.data["overall_weekly_score"])
        self.assertIn(
            "No scored tasks available for this week.",
            preview.data["final_weekly_report_generation_prompt"],
        )
        created = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(created.data["overall_weekly_score"])
        import json

        payload = json.loads(call_log["generator_payloads"][0][1]["content"])
        self.assertNotIn("overall_weekly_score", payload.get("required_fields", []))

    @patch("services.ai.client.parse_structured")
    def test_needs_revision_feedback_and_multiple_versions_reach_context(self, mock_parse):
        self.assignment.status = TaskAssignmentStatus.NEEDS_REVISION
        self.assignment.score = None
        self.assignment.mentor_feedback = "Add tests"
        self.assignment.save()
        Submission.objects.create(
            task_assignment=self.assignment,
            version_number=1,
            written_response="First attempt",
        )
        Submission.objects.create(
            task_assignment=self.assignment,
            version_number=2,
            written_response="Revised attempt",
        )
        self._mock_prompt_only(mock_parse)
        self.auth(self.mentor)
        response = self._build_prompt()
        content = mock_parse.call_args.kwargs["input_messages"][1]["content"]
        self.assertIn("Add tests", content)
        self.assertIn("First attempt", content)
        self.assertIn("Revised attempt", content)
        self.assertIn("No scored tasks available for this week.", response.data["final_weekly_report_generation_prompt"])

    @patch("services.ai.client.parse_structured")
    def test_regenerate_updates_existing_draft(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        first_preview = self._build_prompt()
        first = self.client.post(
            CONTINUE_URL,
            {"preview_id": first_preview.data["preview_id"]},
            format="json",
        )
        second_preview = self._build_prompt()
        second = self.client.post(
            CONTINUE_URL,
            {"preview_id": second_preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(WeeklyReport.objects.filter(intern=self.intern, roadmap_week=self.week).count(), 1)
