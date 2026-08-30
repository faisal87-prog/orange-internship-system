"""Deterministic week-performance comparison tests (no OpenAI)."""

from datetime import date, datetime, timedelta, timezone as dt_timezone

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
from services.week_performance import (
    build_final_summary_week_performance,
    build_final_summary_weeks_completed_tasks,
    build_weekly_report_comparison,
)


class WeekPerformanceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.mentor = User.objects.create_user(
            email="mentor@wp.test",
            username="mentor_wp",
            password="pass1234",
            full_name="Mentor WP",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(user=self.mentor, department="Eng", job_title="Lead")
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="WP Program",
            description="Desc",
            role="Intern",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 7, 26),
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
        self.intern_user = User.objects.create_user(
            email="intern@wp.test",
            username="intern_wp",
            password="pass1234",
            full_name="Intern WP",
            role=Role.INTERN,
        )
        self.intern = InternProfile.objects.create(
            user=self.intern_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn",
        )
        self.other_user = User.objects.create_user(
            email="other@wp.test",
            username="other_wp",
            password="pass1234",
            full_name="Other Intern",
            role=Role.INTERN,
        )
        self.other = InternProfile.objects.create(
            user=self.other_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Other",
        )
        self.roadmap = Roadmap.objects.create(
            program=self.program,
            title="Roadmap",
            summary="Summary",
            assignment_scope=RoadmapScope.PROGRAM,
            number_of_weeks=4,
            status=RoadmapStatus.PUBLISHED,
        )
        self.weeks = []
        for number in range(1, 5):
            week = RoadmapWeek.objects.create(
                roadmap=self.roadmap,
                week_number=number,
                weekly_focus=f"Focus {number}",
                learning_objectives=[f"Obj {number}"],
                expected_skills_gained=[f"Skill {number}"],
                start_date=date(2026, 6, 1) + timedelta(weeks=number - 1),
                end_date=date(2026, 6, 7) + timedelta(weeks=number - 1),
                display_order=number,
            )
            self.weeks.append(week)

    def _make_task(self, week, title, due_day_offset=4):
        return Task.objects.create(
            roadmap_week=week,
            program=self.program,
            created_by=self.mentor,
            title=title,
            description="Desc",
            difficulty=TaskDifficulty.MEDIUM,
            estimated_time_minutes=60,
            due_date=week.start_date + timedelta(days=due_day_offset),
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
        )

    def _assign(
        self,
        task,
        intern,
        *,
        status_value=TaskAssignmentStatus.TO_DO,
        score=None,
        submitted_on=None,
    ):
        assignment = TaskAssignment.objects.create(
            task=task,
            intern=intern,
            status=status_value,
            score=score,
        )
        if submitted_on is not None:
            submission = Submission.objects.create(
                task_assignment=assignment,
                version_number=1,
                written_response="Work",
            )
            Submission.objects.filter(pk=submission.pk).update(
                submitted_at=datetime(
                    submitted_on.year,
                    submitted_on.month,
                    submitted_on.day,
                    12,
                    0,
                    tzinfo=dt_timezone.utc,
                )
            )
        return assignment

    def _approved_report(self, week, score, intern=None):
        return WeeklyReport.objects.create(
            intern=intern or self.intern,
            program=self.program,
            roadmap_week=week,
            performance_summary="Approved weekly report with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail here.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Recommended next focus with enough detail.",
            overall_weekly_score=score,
            status=AiContentStatus.APPROVED,
        )

    def test_week1_has_no_previous_weeks(self):
        comparison = build_weekly_report_comparison(
            intern=self.intern,
            program=self.program,
            current_week=self.weeks[0],
            current_weekly_score=78,
        )
        self.assertFalse(comparison["has_previous_weeks"])
        self.assertEqual(comparison["message"], "No previous week available for comparison.")
        self.assertEqual(len(comparison["weeks"]), 1)
        self.assertIsNone(comparison["change"])

    def test_week2_includes_week1_and_week2_with_change(self):
        self._approved_report(self.weeks[0], 78)
        task1 = self._make_task(self.weeks[0], "W1 Task")
        self._assign(
            task1,
            self.intern,
            status_value=TaskAssignmentStatus.COMPLETED,
            score=78,
            submitted_on=self.weeks[0].start_date + timedelta(days=1),
        )
        task2 = self._make_task(self.weeks[1], "W2 Task")
        self._assign(
            task2,
            self.intern,
            status_value=TaskAssignmentStatus.COMPLETED,
            score=84,
            submitted_on=self.weeks[1].start_date + timedelta(days=1),
        )
        comparison = build_weekly_report_comparison(
            intern=self.intern,
            program=self.program,
            current_week=self.weeks[1],
            current_weekly_score=84,
        )
        self.assertTrue(comparison["has_previous_weeks"])
        self.assertEqual([w["week_number"] for w in comparison["weeks"]], [1, 2])
        self.assertEqual(comparison["change"]["weekly_score"], 6)
        self.assertEqual(comparison["change"]["completed_tasks"], 0)

    def test_week3_and_week4_include_all_prior_weeks(self):
        for week, score in zip(self.weeks[:3], [78, 84, 89]):
            self._approved_report(week, score)
        comparison3 = build_weekly_report_comparison(
            intern=self.intern,
            program=self.program,
            current_week=self.weeks[2],
            current_weekly_score=89,
        )
        self.assertEqual([w["week_number"] for w in comparison3["weeks"]], [1, 2, 3])
        self.assertEqual(comparison3["change"]["weekly_score"], 5)

        self._approved_report(self.weeks[3], 91)
        comparison4 = build_weekly_report_comparison(
            intern=self.intern,
            program=self.program,
            current_week=self.weeks[3],
            current_weekly_score=91,
        )
        self.assertEqual([w["week_number"] for w in comparison4["weeks"]], [1, 2, 3, 4])
        self.assertEqual(comparison4["change"]["weekly_score"], 2)

    def test_missing_historical_score_is_null_not_zero(self):
        comparison = build_weekly_report_comparison(
            intern=self.intern,
            program=self.program,
            current_week=self.weeks[1],
            current_weekly_score=84,
        )
        self.assertIsNone(comparison["weeks"][0]["weekly_score"])
        self.assertEqual(comparison["weeks"][1]["weekly_score"], 84)
        self.assertIsNone(comparison["change"]["weekly_score"])

    def test_task_counts_and_on_time_and_isolation(self):
        week = self.weeks[0]
        task_a = self._make_task(week, "A")
        task_b = self._make_task(week, "B")
        task_c = self._make_task(week, "C")
        self._assign(
            task_a,
            self.intern,
            status_value=TaskAssignmentStatus.COMPLETED,
            submitted_on=week.start_date + timedelta(days=1),
        )
        self._assign(
            task_b,
            self.intern,
            status_value=TaskAssignmentStatus.NEEDS_REVISION,
        )
        assignment_b = TaskAssignment.objects.get(task=task_b, intern=self.intern)
        submission_b = Submission.objects.create(
            task_assignment=assignment_b,
            version_number=1,
            written_response="Late",
        )
        Submission.objects.filter(pk=submission_b.pk).update(
            submitted_at=datetime(
                week.start_date.year,
                week.start_date.month,
                week.start_date.day,
                12,
                tzinfo=dt_timezone.utc,
            )
            + timedelta(days=10),
        )
        self._assign(task_c, self.intern, status_value=TaskAssignmentStatus.TO_DO)
        # Other intern noise
        self._assign(
            task_a,
            self.other,
            status_value=TaskAssignmentStatus.COMPLETED,
            submitted_on=week.start_date + timedelta(days=1),
        )

        comparison = build_weekly_report_comparison(
            intern=self.intern,
            program=self.program,
            current_week=week,
            current_weekly_score=70,
        )
        row = comparison["weeks"][0]
        self.assertEqual(row["completed_tasks"], 1)
        self.assertEqual(row["total_tasks"], 3)
        self.assertEqual(row["needs_revision"], 1)
        self.assertEqual(row["on_time_tasks"], 1)

    def test_weekly_report_api_exposes_comparison(self):
        self._approved_report(self.weeks[0], 78)
        report = WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.weeks[1],
            performance_summary="Draft weekly report with enough detail.",
            achievements=["Done"],
            learning_progress="Learning progress with enough detail here.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Recommended next focus with enough detail.",
            overall_weekly_score=84,
            status=AiContentStatus.DRAFT,
        )
        self.client.force_authenticate(user=self.mentor)
        response = self.client.get(f"/api/reports/weekly/{report.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comparison = response.data["performance_comparison"]
        self.assertTrue(comparison["has_previous_weeks"])
        self.assertEqual(len(comparison["weeks"]), 2)
        self.assertEqual(comparison["change"]["weekly_score"], 6)

    def test_final_summary_week_performance_all_weeks(self):
        self._approved_report(self.weeks[0], 78)
        self._approved_report(self.weeks[1], 84)
        WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.weeks[2],
            performance_summary="Draft weekly report with enough detail.",
            achievements=["Draft"],
            learning_progress="Learning progress with enough detail here.",
            productivity_analysis="Productivity analysis with enough detail.",
            mentor_focus_suggestions=["Focus"],
            recommended_next_focus="Recommended next focus with enough detail.",
            overall_weekly_score=99,
            status=AiContentStatus.DRAFT,
        )
        task = self._make_task(self.weeks[0], "FS Task")
        self._assign(
            task,
            self.intern,
            status_value=TaskAssignmentStatus.NEEDS_REVISION,
            submitted_on=self.weeks[0].start_date + timedelta(days=1),
        )

        payload = build_final_summary_week_performance(
            intern=self.intern,
            program=self.program,
        )
        weeks = payload["weeks"]
        self.assertEqual([row["week_number"] for row in weeks], [1, 2, 3, 4])
        self.assertEqual(weeks[0]["weekly_score"], 78)
        self.assertEqual(weeks[1]["weekly_score"], 84)
        self.assertIsNone(weeks[2]["weekly_score"])  # draft excluded
        self.assertIsNone(weeks[3]["weekly_score"])
        self.assertEqual(weeks[0]["main_focus"], "Focus 1")
        self.assertEqual(weeks[0]["needs_revision"], 1)
        self.assertEqual(weeks[0]["completed_tasks"], 0)
        self.assertEqual(weeks[0]["total_tasks"], 1)

        summary = FinalInternshipSummary.objects.create(
            intern=self.intern,
            program=self.program,
            overall_performance_summary="Overall summary with enough detail for tests.",
            learning_journey="Learning journey with enough detail for tests.",
            main_achievements=["Achievement"],
            goal_achievement="Goal achievement with enough detail for tests.",
            final_performance_summary="Final performance with enough detail for tests.",
            status=AiContentStatus.DRAFT,
        )
        self.client.force_authenticate(user=self.mentor)
        response = self.client.get(f"/api/reports/final-summaries/{summary.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["week_performance"]["weeks"]), 4)
        self.assertEqual(response.data["final_score"], 81.0)  # (78+84)/2

    def test_final_summary_weeks_completed_tasks_table(self):
        week1, week2, week3, week4 = self.weeks
        task_done = self._make_task(week1, "Build Inquiry Model")
        task_open = self._make_task(week1, "Still Open")
        task_week2 = self._make_task(week2, "Integrate OpenAI")
        task_week3 = self._make_task(week3, "Empty Week Task")
        self._assign(
            task_done,
            self.intern,
            status_value=TaskAssignmentStatus.COMPLETED,
            submitted_on=week1.start_date + timedelta(days=1),
        )
        self._assign(task_open, self.intern, status_value=TaskAssignmentStatus.TO_DO)
        self._assign(
            task_week2,
            self.intern,
            status_value=TaskAssignmentStatus.COMPLETED,
            submitted_on=week2.start_date + timedelta(days=1),
        )
        self._assign(task_week3, self.intern, status_value=TaskAssignmentStatus.TO_DO)
        # Other intern completed noise must not appear.
        self._assign(
            task_done,
            self.other,
            status_value=TaskAssignmentStatus.COMPLETED,
            submitted_on=week1.start_date + timedelta(days=1),
        )

        payload = build_final_summary_weeks_completed_tasks(
            intern=self.intern,
            program=self.program,
        )
        weeks = payload["weeks"]
        self.assertEqual([row["week_number"] for row in weeks], [1, 2, 3, 4])
        self.assertEqual(weeks[0]["main_focus"], "Focus 1")
        self.assertEqual(weeks[0]["completed_task_titles"], ["Build Inquiry Model"])
        self.assertEqual(weeks[1]["completed_task_titles"], ["Integrate OpenAI"])
        self.assertEqual(weeks[2]["completed_task_titles"], [])
        self.assertEqual(weeks[3]["completed_task_titles"], [])
        self.assertEqual(weeks[3]["main_focus"], "Focus 4")

        summary = FinalInternshipSummary.objects.create(
            intern=self.intern,
            program=self.program,
            internship_introduction="Program purpose with enough detail for tests.",
            training_summary="Training overview with enough detail for tests.",
            overall_performance_summary="Overall summary with enough detail for tests.",
            learning_journey="Learning journey with enough detail for tests.",
            main_achievements=["Achievement"],
            goal_achievement="Goal achievement with enough detail for tests.",
            final_performance_summary="Final performance with enough detail for tests.",
            status=AiContentStatus.DRAFT,
        )
        self.client.force_authenticate(user=self.mentor)
        response = self.client.get(f"/api/reports/final-summaries/{summary.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data["weeks_completed_tasks"]["weeks"]
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["completed_task_titles"], ["Build Inquiry Model"])
        self.assertEqual(response.data["mentor_name"], "Mentor WP")
        # Performance table still present and separate.
        self.assertEqual(len(response.data["week_performance"]["weeks"]), 4)
        blob = str(response.data["weeks_completed_tasks"])
        self.assertNotIn("mentor_feedback", blob)
        self.assertNotIn("Good work", blob)