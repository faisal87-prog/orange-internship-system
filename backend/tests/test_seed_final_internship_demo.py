"""Focused isolation tests for seed_final_internship_demo management command."""

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import MentorProfile, User
from apps.programs.models import InternProfile, InternshipProgram
from apps.reports.models import FinalInternshipSummary, WeeklyReport
from apps.roadmaps.models import Roadmap, RoadmapWeek
from apps.submissions.models import Submission
from apps.tasks.models import Task, TaskAssignment
from common.constants import (
    ProgramStatus,
    RequirementType,
    Role,
    RoadmapScope,
    RoadmapStatus,
    TaskAssignmentStatus,
    TaskDifficulty,
    TaskSource,
)


PROGRAM_TITLE = "AI Internship Management Platform Development"


class SeedFinalInternshipDemoTests(TestCase):
    def setUp(self):
        self.mentor = User.objects.create_user(
            email="ahmad@seed.test",
            username="ahmad_seed",
            password="pass1234",
            full_name="Ahmad Mashaaleh",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.mentor, department="AI", job_title="Lead Mentor"
        )
        self.other_mentor = User.objects.create_user(
            email="other.mentor@seed.test",
            username="other_mentor_seed",
            password="pass1234",
            full_name="Other Mentor",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.other_mentor, department="Eng", job_title="Mentor"
        )

        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title=PROGRAM_TITLE,
            description="Target program",
            role="Intern",
            start_date=date(2026, 7, 22),
            end_date=date(2026, 9, 1),
            duration_weeks=6,
            department="Artificial Intelligence",
            weekly_hours=40,
            maximum_interns=5,
            goals="Ship",
            skills_to_develop=["APIs"],
            expected_outcome="Ready",
            final_project="Capstone",
            status=ProgramStatus.ACTIVE,
        )
        self.other_program = InternshipProgram.objects.create(
            mentor=self.other_mentor,
            title="Unrelated Other Program",
            description="Must not be touched",
            role="Intern",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 12),
            duration_weeks=6,
            department="Other",
            weekly_hours=20,
            maximum_interns=3,
            status=ProgramStatus.ACTIVE,
        )

        self.faisal_user = User.objects.create_user(
            email="faisal@seed.test",
            username="faisal_seed",
            password="pass1234",
            full_name="Faisal Quntar",
            role=Role.INTERN,
        )
        self.samir_user = User.objects.create_user(
            email="samir@seed.test",
            username="samir_seed",
            password="pass1234",
            full_name="Samir Aboud",
            role=Role.INTERN,
        )
        self.third_user = User.objects.create_user(
            email="third@seed.test",
            username="third_seed",
            password="pass1234",
            full_name="Third Intern",
            role=Role.INTERN,
        )
        self.foreign_user = User.objects.create_user(
            email="foreign@seed.test",
            username="foreign_seed",
            password="pass1234",
            full_name="Foreign Intern",
            role=Role.INTERN,
        )

        self.faisal = InternProfile.objects.create(
            user=self.faisal_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn",
        )
        self.samir = InternProfile.objects.create(
            user=self.samir_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn",
        )
        self.third = InternProfile.objects.create(
            user=self.third_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn",
        )
        self.foreign = InternProfile.objects.create(
            user=self.foreign_user,
            mentor=self.other_mentor,
            program=self.other_program,
            learning_goals="Learn",
        )

        self.roadmap = Roadmap.objects.create(
            program=self.program,
            title="Published Target Roadmap",
            summary="Summary",
            assignment_scope=RoadmapScope.PROGRAM,
            number_of_weeks=6,
            status=RoadmapStatus.PUBLISHED,
        )
        self.other_roadmap = Roadmap.objects.create(
            program=self.other_program,
            title="Other Published Roadmap",
            summary="Other",
            assignment_scope=RoadmapScope.PROGRAM,
            number_of_weeks=1,
            status=RoadmapStatus.PUBLISHED,
        )
        self.weeks = []
        for number in range(1, 7):
            week = RoadmapWeek.objects.create(
                roadmap=self.roadmap,
                week_number=number,
                weekly_focus=f"Focus {number}",
                start_date=date(2026, 7, 22) + timedelta(days=(number - 1) * 7),
                end_date=date(2026, 7, 28) + timedelta(days=(number - 1) * 7),
                display_order=number,
            )
            self.weeks.append(week)

        self.tasks = self._create_tasks(count=20)
        self._assign_targets()

        # Unrelated task + assignments that must never be touched.
        other_week = RoadmapWeek.objects.create(
            roadmap=self.other_roadmap,
            week_number=1,
            weekly_focus="Other",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 7),
            display_order=1,
        )
        self.other_task = Task.objects.create(
            roadmap_week=other_week,
            program=self.other_program,
            created_by=self.other_mentor,
            title="Other Program Task",
            description="Must not change",
            difficulty=TaskDifficulty.EASY,
            estimated_time_minutes=60,
            due_date=date(2026, 1, 5),
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
        )
        self.other_assignment = TaskAssignment.objects.create(
            task=self.other_task,
            intern=self.foreign,
            status=TaskAssignmentStatus.TO_DO,
        )
        self.third_assignment = TaskAssignment.objects.create(
            task=self.tasks[0],
            intern=self.third,
            status=TaskAssignmentStatus.TO_DO,
        )

    def _create_tasks(self, count: int) -> list[Task]:
        tasks = []
        for index in range(count):
            week = self.weeks[index % len(self.weeks)]
            task = Task.objects.create(
                roadmap_week=week,
                program=self.program,
                created_by=self.mentor,
                title=f"Target Task {index + 1}",
                description=f"Description {index + 1}",
                difficulty=TaskDifficulty.MEDIUM,
                estimated_time_minutes=120,
                due_date=week.start_date + timedelta(days=2),
                requirement_type=RequirementType.REQUIRED,
                source=TaskSource.AI_GENERATED,
                display_order=index + 1,
            )
            tasks.append(task)
        return tasks

    def _assign_targets(self):
        for task in self.tasks:
            TaskAssignment.objects.get_or_create(task=task, intern=self.faisal)
            TaskAssignment.objects.get_or_create(task=task, intern=self.samir)

    def _run(self):
        out = StringIO()
        call_command("seed_final_internship_demo", stdout=out)
        return out.getvalue()

    def test_seeds_only_target_interns_and_tasks(self):
        weekly_before = WeeklyReport.objects.count()
        final_before = FinalInternshipSummary.objects.count()
        other_status_before = self.other_assignment.status
        third_status_before = self.third_assignment.status

        output = self._run()
        self.assertIn("TARGET VALIDATION PASSED", output)
        self.assertIn(PROGRAM_TITLE, output)
        self.assertIn("Ahmad Mashaaleh", output)
        self.assertIn("Faisal Quntar", output)
        self.assertIn("Samir Aboud", output)
        self.assertIn("Tasks found:\n20", output)

        faisal_done = TaskAssignment.objects.filter(
            intern=self.faisal,
            task__in=self.tasks,
            status=TaskAssignmentStatus.COMPLETED,
        )
        samir_done = TaskAssignment.objects.filter(
            intern=self.samir,
            task__in=self.tasks,
            status=TaskAssignmentStatus.COMPLETED,
        )
        self.assertEqual(faisal_done.count(), 20)
        self.assertEqual(samir_done.count(), 20)

        for assignment in list(faisal_done) + list(samir_done):
            self.assertIsNotNone(assignment.score)
            self.assertGreaterEqual(assignment.score, 85)
            self.assertLessEqual(assignment.score, 100)
            self.assertTrue(assignment.mentor_feedback.strip())
            self.assertIsNotNone(assignment.reviewed_at)
            submission = assignment.submissions.get()
            self.assertIn("AI Internship Management Platform", submission.written_response)
            self.assertEqual(submission.external_url, "")
            self.assertLessEqual(submission.submitted_at.date(), assignment.effective_due_date)

        # Separate assignment rows per intern
        self.assertEqual(
            TaskAssignment.objects.filter(task=self.tasks[0], intern=self.faisal).count(),
            1,
        )
        self.assertEqual(
            TaskAssignment.objects.filter(task=self.tasks[0], intern=self.samir).count(),
            1,
        )
        self.assertNotEqual(
            TaskAssignment.objects.get(task=self.tasks[0], intern=self.faisal).id,
            TaskAssignment.objects.get(task=self.tasks[0], intern=self.samir).id,
        )

        # Third intern in same program untouched
        self.third_assignment.refresh_from_db()
        self.assertEqual(self.third_assignment.status, third_status_before)
        self.assertFalse(self.third_assignment.submissions.exists())
        self.assertIsNone(self.third_assignment.score)

        # Other program/intern untouched
        self.other_assignment.refresh_from_db()
        self.assertEqual(self.other_assignment.status, other_status_before)
        self.assertFalse(self.other_assignment.submissions.exists())

        self.assertEqual(WeeklyReport.objects.count(), weekly_before)
        self.assertEqual(FinalInternshipSummary.objects.count(), final_before)
        self.assertIn("Weekly Reports created:\n0", output)
        self.assertIn("Final Summaries created:\n0", output)
        self.assertIn("Unrelated Programs modified:\n0", output)

        # Scores vary (deterministic seed)
        scores = list(faisal_done.values_list("score", flat=True)) + list(
            samir_done.values_list("score", flat=True)
        )
        self.assertGreater(len(set(scores)), 1)

    def test_wrong_task_count_aborts_with_zero_writes(self):
        # Create 21st task on target roadmap
        Task.objects.create(
            roadmap_week=self.weeks[0],
            program=self.program,
            created_by=self.mentor,
            title="Extra Task 21",
            description="Extra",
            difficulty=TaskDifficulty.EASY,
            estimated_time_minutes=30,
            due_date=self.weeks[0].start_date,
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
        )
        before_subs = Submission.objects.count()
        with self.assertRaises(CommandError) as raised:
            self._run()
        self.assertIn("Expected exactly 20 tasks", str(raised.exception))
        self.assertIn("found 21", str(raised.exception))
        self.assertEqual(Submission.objects.count(), before_subs)
        self.assertEqual(
            TaskAssignment.objects.filter(
                intern__in=[self.faisal, self.samir],
                status=TaskAssignmentStatus.COMPLETED,
            ).count(),
            0,
        )

    def test_nineteen_tasks_aborts(self):
        Task.objects.filter(pk=self.tasks[-1].pk).delete()
        before_subs = Submission.objects.count()
        with self.assertRaises(CommandError) as raised:
            self._run()
        self.assertIn("Expected exactly 20 tasks", str(raised.exception))
        self.assertIn("found 19", str(raised.exception))
        self.assertEqual(Submission.objects.count(), before_subs)

    def test_wrong_mentor_aborts(self):
        self.program.mentor = self.other_mentor
        self.program.save(update_fields=["mentor"])
        with self.assertRaises(CommandError) as raised:
            self._run()
        self.assertIn("Program Mentor must be 'Ahmad Mashaaleh'", str(raised.exception))

    def test_missing_exact_program_title_aborts(self):
        self.program.title = "Almost AI Internship Management Platform Development"
        self.program.save(update_fields=["title"])
        with self.assertRaises(CommandError) as raised:
            self._run()
        self.assertIn("not found", str(raised.exception).lower())

    def test_existing_history_skipped_and_rerun_no_duplicates(self):
        output1 = self._run()
        self.assertIn("Processed: 20", output1)
        sub_count = Submission.objects.filter(
            task_assignment__intern__in=[self.faisal, self.samir],
            task_assignment__task__in=self.tasks,
        ).count()
        self.assertEqual(sub_count, 40)

        output2 = self._run()
        self.assertIn("SKIPPED — existing task history found", output2)
        self.assertIn("Processed: 0", output2)
        self.assertIn("Skipped: 20", output2)
        self.assertEqual(
            Submission.objects.filter(
                task_assignment__intern__in=[self.faisal, self.samir],
                task_assignment__task__in=self.tasks,
            ).count(),
            40,
        )

    def test_other_program_task_not_processed(self):
        self._run()
        self.other_assignment.refresh_from_db()
        self.assertEqual(self.other_assignment.status, TaskAssignmentStatus.TO_DO)
        self.assertIsNone(self.other_assignment.score)
        self.assertFalse(
            Submission.objects.filter(task_assignment=self.other_assignment).exists()
        )
