"""AI final internship summary two-step generation tests — OpenAI fully mocked."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import MentorProfile, User
from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import FinalInternshipSummary, WeeklyReport
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
from services.ai.schemas import (
    GeneratedFinalSummary,
    GeneratedFinalSummaryPrompt,
    GeneratedWeeklyReportPrompt,
)
from services.pdf import final_summary_pdf_filename, final_summary_title

PROMPT_URL = "/api/reports/final-summaries/generate/prompt/"
CONTINUE_URL = "/api/reports/final-summaries/generate/continue/"


def build_prompt() -> GeneratedFinalSummaryPrompt:
    return GeneratedFinalSummaryPrompt(
        prompt_title="Final internship prompt",
        final_summary_generation_prompt=(
            "Write an evidence-based final internship summary for the selected intern. "
            "Do not invent scores, achievements, or hiring recommendations."
        ),
        important_constraints=["Use supplied evidence only", "Do not invent final score"],
        personalization_points=["Relate progress to program goals"],
        missing_context_notes=["Preferences unavailable"],
    )


def build_summary() -> GeneratedFinalSummary:
    return GeneratedFinalSummary(
        overall_performance_summary=(
            "The intern completed required work with consistent quality across the program."
        ),
        learning_journey=(
            "Progress moved from guided early tasks toward more independent later submissions."
        ),
        main_achievements="Completed the API task\nAddressed mentor revision feedback",
        goal_achievement=(
            "Program goals were partially demonstrated through completed tasks and feedback."
        ),
        final_performance_summary=(
            "Available evidence shows solid completion patterns without unsupported claims."
        ),
    )


class AIFinalSummaryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@fs.test",
            username="admin_fs",
            password="pass1234",
            full_name="Admin",
            role=Role.ADMIN,
            is_staff=True,
        )
        self.mentor = User.objects.create_user(
            email="mentor@fs.test",
            username="mentor_fs",
            password="pass1234",
            full_name="Mentor FS",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(user=self.mentor, department="Eng", job_title="Lead")
        self.other_mentor = User.objects.create_user(
            email="other@fs.test",
            username="other_fs",
            password="pass1234",
            full_name="Other Mentor",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.other_mentor, department="Design", job_title="Lead"
        )
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="FS Program",
            description="Desc",
            role="Intern",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 7, 26),
            duration_weeks=8,
            department="Engineering",
            weekly_hours=20,
            maximum_interns=3,
            goals="Ship reliable APIs",
            skills_needed=["Python"],
            skills_to_develop=["APIs", "Testing"],
            expected_outcome="Independent contributor",
            final_project="Capstone API",
            status=ProgramStatus.ACTIVE,
        )
        self.intern_user = User.objects.create_user(
            email="intern@fs.test",
            username="intern_fs",
            password="pass1234",
            full_name="Samir Aboud",
            role=Role.INTERN,
        )
        self.intern = InternProfile.objects.create(
            user=self.intern_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn APIs",
            major="CS",
            university="Test U",
        )
        self.intern_b_user = User.objects.create_user(
            email="internb@fs.test",
            username="internb_fs",
            password="pass1234",
            full_name="Intern B Private",
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
            number_of_weeks=2,
            status=RoadmapStatus.PUBLISHED,
        )
        self.week1 = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=1,
            weekly_focus="APIs",
            learning_objectives=["Build endpoints"],
            expected_skills_gained=["REST"],
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            display_order=1,
        )
        self.week2 = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=2,
            weekly_focus="Testing",
            learning_objectives=["Write tests"],
            expected_skills_gained=["pytest"],
            start_date=date(2026, 6, 8),
            end_date=date(2026, 6, 14),
            display_order=2,
        )
        self.task = Task.objects.create(
            roadmap_week=self.week1,
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
            status=TaskAssignmentStatus.COMPLETED,
            score=99,
            mentor_feedback="Intern B private feedback",
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.week1,
            performance_summary="Solid week one delivery.",
            achievements=["Shipped endpoint"],
            learning_progress="Grew API confidence.",
            productivity_analysis="Completed required work.",
            mentor_focus_suggestions=["Continue testing"],
            recommended_next_focus="Add tests",
            overall_weekly_score=80,
            additional_mentor_notes="Keep going",
            status=AiContentStatus.APPROVED,
            generated_by_ai=True,
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.week2,
            performance_summary="Draft week two.",
            achievements=["Draft only"],
            learning_progress="Draft",
            productivity_analysis="Draft",
            mentor_focus_suggestions=["Draft"],
            recommended_next_focus="Draft",
            overall_weekly_score=70,
            status=AiContentStatus.DRAFT,
            generated_by_ai=True,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def _mock_prompt_only(self, mock_parse):
        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedFinalSummaryPrompt:
                return build_prompt()
            if text_format is GeneratedWeeklyReportPrompt:
                raise AssertionError("Weekly prompt builder must not be used")
            raise AssertionError("Call #2 must not run during prompt preview")

        mock_parse.side_effect = side_effect

    def _mock_full(self, mock_parse):
        call_log = {"generator_payloads": []}

        def side_effect(*, model, input_messages, text_format):
            if text_format is GeneratedFinalSummaryPrompt:
                return build_prompt()
            if text_format is GeneratedFinalSummary:
                call_log["generator_payloads"].append(input_messages)
                return build_summary()
            raise AssertionError(f"Unexpected schema {text_format}")

        mock_parse.side_effect = side_effect
        return call_log

    def _build_prompt(self, **extra):
        payload = {
            "program_id": self.program.id,
            "intern_id": self.intern.id,
            **extra,
        }
        return self.client.post(PROMPT_URL, payload, format="json")

    @patch("services.ai.client.parse_structured")
    def test_step1_context_isolation_and_no_persistence(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        self.auth(self.mentor)
        before = FinalInternshipSummary.objects.count()
        response = self._build_prompt()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("preview_id", response.data)
        self.assertEqual(FinalInternshipSummary.objects.count(), before)
        self.assertEqual(mock_parse.call_count, 1)
        self.assertIs(
            mock_parse.call_args.kwargs["text_format"],
            GeneratedFinalSummaryPrompt,
        )
        content = mock_parse.call_args.kwargs["input_messages"][1]["content"]
        self.assertIn("Samir Aboud", content)
        self.assertIn("API Task", content)
        self.assertIn("Ship reliable APIs", content)
        self.assertIn("Capstone API", content)
        self.assertIn("Solid week one delivery.", content)
        self.assertNotIn("Draft week two.", content)
        self.assertNotIn("Intern B private feedback", content)
        self.assertNotIn('"score": 99', content)
        final_prompt = response.data["final_final_summary_generation_prompt"]
        self.assertIn("PROGRAM CONTEXT", final_prompt)
        self.assertIn("APPROVED WEEKLY REPORTS", final_prompt)
        self.assertIn("Do NOT invent or output an official Final Score.", final_prompt)

    @patch("services.ai.client.parse_structured")
    def test_continue_uses_exact_prompt_and_creates_draft(self, mock_parse):
        call_log = self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        final_prompt = preview.data["final_final_summary_generation_prompt"]
        response = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], AiContentStatus.DRAFT)
        self.assertTrue(response.data["generated_by_ai"])
        self.assertEqual(response.data["final_score"], 80.0)
        self.assertEqual(response.data["scored_weekly_report_count"], 1)
        self.assertEqual(response.data["mentor_comments"], "")
        self.assertEqual(response.data["additional_mentor_notes"], "")
        self.assertIn("overall_performance_summary", response.data)
        self.assertNotIn("strengths", response.data)
        import json

        payload = json.loads(call_log["generator_payloads"][0][1]["content"])
        self.assertEqual(
            payload["final_final_summary_generation_prompt"],
            final_prompt,
        )
        self.assertNotIn("final_score", payload.get("required_fields", []))

        self.auth(self.intern_user)
        listed = self.client.get("/api/reports/final-summaries/")
        rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        self.assertEqual(rows, [])

    @patch("services.ai.client.parse_structured")
    def test_permissions(self, mock_parse):
        self._mock_prompt_only(mock_parse)
        payload = {
            "program_id": self.program.id,
            "intern_id": self.intern.id,
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
    def test_mentor_fields_approval_visibility_and_pdf(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        created = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        summary_id = created.data["id"]
        patched = self.client.patch(
            f"/api/reports/final-summaries/{summary_id}/",
            {
                "final_score": 87,
                "mentor_comments": "Strong ownership.",
                "additional_mentor_notes": "Ready for next steps with mentoring.",
                "overall_performance_summary": "Edited overall summary with enough detail.",
            },
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        # Mentor cannot override Final Score; remains Django weekly average.
        self.assertEqual(patched.data["final_score"], 80.0)
        self.assertEqual(patched.data["mentor_comments"], "Strong ownership.")

        draft_pdf = self.client.get(
            f"/api/reports/final-summaries/{summary_id}/download_pdf/"
        )
        self.assertEqual(draft_pdf.status_code, status.HTTP_200_OK)

        approved = self.client.post(
            f"/api/reports/final-summaries/{summary_id}/approve/", {}, format="json"
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(approved.data["status"], AiContentStatus.APPROVED)
        self.assertTrue(approved.data["pdf_url"])

        self.auth(self.intern_user)
        listed = self.client.get("/api/reports/final-summaries/")
        rows = listed.data["results"] if isinstance(listed.data, dict) else listed.data
        self.assertEqual(len(rows), 1)
        pdf = self.client.get(f"/api/reports/final-summaries/{summary_id}/download_pdf/")
        self.assertEqual(pdf.status_code, status.HTTP_200_OK)
        summary = FinalInternshipSummary.objects.get(id=summary_id)
        self.assertTrue(
            Path(summary.pdf_file.name).name.startswith(
                "final-internship-summary-samir-aboud"
            )
        )
        disposition = pdf.get("Content-Disposition", "")
        self.assertIn("final-internship-summary-samir-aboud.pdf", disposition)

        self.auth(self.admin)
        approve_again = self.client.post(
            f"/api/reports/final-summaries/{summary_id}/approve/", {}, format="json"
        )
        self.assertEqual(approve_again.status_code, status.HTTP_403_FORBIDDEN)

    def test_pdf_title_and_filename_helpers(self):
        summary = FinalInternshipSummary(
            intern=self.intern,
            program=self.program,
        )
        self.assertEqual(
            final_summary_title(summary),
            "Final Internship Summary for Samir Aboud",
        )
        self.assertEqual(
            final_summary_pdf_filename(summary),
            "final-internship-summary-samir-aboud.pdf",
        )

    @patch("services.ai.client.parse_structured")
    def test_needs_revision_and_multiple_versions_in_context(self, mock_parse):
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
        self.assertIn("needs_revision", content)
        self.assertIn(
            "Do NOT invent or output an official Final Score.",
            response.data["final_final_summary_generation_prompt"],
        )

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
        self.client.patch(
            f"/api/reports/final-summaries/{first.data['id']}/",
            {"mentor_comments": "Keep this note", "final_score": 75},
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
        self.assertEqual(
            FinalInternshipSummary.objects.filter(
                intern=self.intern, program=self.program
            ).count(),
            1,
        )
        summary = FinalInternshipSummary.objects.get(id=first.data["id"])
        self.assertEqual(summary.mentor_comments, "Keep this note")
        self.assertEqual(float(summary.final_score), 80.0)

    @patch("services.ai.client.parse_structured")
    def test_cannot_regenerate_approved(self, mock_parse):
        self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        created = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        self.client.post(
            f"/api/reports/final-summaries/{created.data['id']}/approve/",
            {},
            format="json",
        )
        again_preview = self._build_prompt()
        again = self.client.post(
            CONTINUE_URL,
            {"preview_id": again_preview.data["preview_id"]},
            format="json",
        )
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)

    def test_final_score_averages_approved_weekly_scores(self):
        from decimal import Decimal

        from services.final_summary_score import (
            calculate_final_summary_score,
            format_final_summary_score_display,
        )

        WeeklyReport.objects.filter(intern=self.intern).delete()
        for week, score in [
            (self.week1, 80),
            (self.week2, 90),
        ]:
            WeeklyReport.objects.create(
                intern=self.intern,
                program=self.program,
                roadmap_week=week,
                performance_summary="Approved week summary with enough detail.",
                achievements=["Done"],
                learning_progress="Learning progress with enough detail.",
                productivity_analysis="Productivity analysis with enough detail.",
                mentor_focus_suggestions=["Focus"],
                recommended_next_focus="Next focus with enough detail.",
                overall_weekly_score=score,
                status=AiContentStatus.APPROVED,
            )
        week3 = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=3,
            weekly_focus="Week 3",
            learning_objectives=["Obj"],
            expected_skills_gained=["Skill"],
            start_date=date(2026, 6, 15),
            end_date=date(2026, 6, 21),
            display_order=3,
        )
        week4 = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=4,
            weekly_focus="Week 4",
            learning_objectives=["Obj"],
            expected_skills_gained=["Skill"],
            start_date=date(2026, 6, 22),
            end_date=date(2026, 6, 28),
            display_order=4,
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=week3,
            performance_summary="Approved week summary with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Next focus with enough detail.",
            overall_weekly_score=85,
            status=AiContentStatus.APPROVED,
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=week4,
            performance_summary="Approved week summary with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Next focus with enough detail.",
            overall_weekly_score=95,
            status=AiContentStatus.APPROVED,
        )
        score = calculate_final_summary_score(self.intern, self.program)
        self.assertEqual(score, Decimal("87.5"))
        self.assertEqual(format_final_summary_score_display(score), "87.5 / 100")

    def test_final_score_excludes_null_and_draft_weekly_scores(self):
        from decimal import Decimal

        from services.final_summary_score import calculate_final_summary_score

        WeeklyReport.objects.filter(intern=self.intern).delete()
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.week1,
            performance_summary="Approved week summary with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Next focus with enough detail.",
            overall_weekly_score=80,
            status=AiContentStatus.APPROVED,
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.week2,
            performance_summary="Approved week summary with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Next focus with enough detail.",
            overall_weekly_score=None,
            status=AiContentStatus.APPROVED,
        )
        week3 = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=3,
            weekly_focus="Week 3",
            learning_objectives=["Obj"],
            expected_skills_gained=["Skill"],
            start_date=date(2026, 6, 15),
            end_date=date(2026, 6, 21),
            display_order=3,
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=week3,
            performance_summary="Approved week summary with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Next focus with enough detail.",
            overall_weekly_score=90,
            status=AiContentStatus.APPROVED,
        )
        week4 = RoadmapWeek.objects.create(
            roadmap=self.roadmap,
            week_number=4,
            weekly_focus="Draft week",
            learning_objectives=["Obj"],
            expected_skills_gained=["Skill"],
            start_date=date(2026, 6, 22),
            end_date=date(2026, 6, 28),
            display_order=4,
        )
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=week4,
            performance_summary="Draft week summary with enough detail.",
            achievements=["Draft"],
            learning_progress="Learning progress with enough detail.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Next focus with enough detail.",
            overall_weekly_score=99,
            status=AiContentStatus.DRAFT,
        )
        score = calculate_final_summary_score(self.intern, self.program)
        self.assertEqual(score, Decimal("85.0"))

    def test_final_score_null_when_no_scored_approved_weeks(self):
        from services.final_summary_score import (
            calculate_final_summary_score,
            format_final_summary_score_display,
        )

        WeeklyReport.objects.filter(intern=self.intern).delete()
        self.assertIsNone(calculate_final_summary_score(self.intern, self.program))
        self.assertEqual(
            format_final_summary_score_display(None),
            "No scored weeks available",
        )

    @patch("services.ai.client.parse_structured")
    def test_pdf_uses_calculated_final_score(self, mock_parse):
        from decimal import Decimal
        from unittest.mock import patch as mock_patch

        from services.final_summary_score import format_final_summary_score_display
        from services.pdf import generate_final_summary_pdf

        self._mock_full(mock_parse)
        self.auth(self.mentor)
        preview = self._build_prompt()
        created = self.client.post(
            CONTINUE_URL,
            {"preview_id": preview.data["preview_id"]},
            format="json",
        )
        summary_id = created.data["id"]
        self.client.post(
            f"/api/reports/final-summaries/{summary_id}/approve/",
            {},
            format="json",
        )
        summary = FinalInternshipSummary.objects.get(id=summary_id)
        self.assertEqual(
            format_final_summary_score_display(summary.final_score),
            "80 / 100",
        )
        with mock_patch(
            "services.final_summary_score.refresh_final_summary_score",
            return_value=Decimal("80.0"),
        ) as mock_refresh, mock_patch(
            "services.final_summary_score.format_final_summary_score_display",
            return_value="80 / 100",
        ) as mock_display:
            generate_final_summary_pdf(summary)
            mock_refresh.assert_called()
            mock_display.assert_called_with(Decimal("80.0"))
        self.assertTrue(summary.pdf_file)
