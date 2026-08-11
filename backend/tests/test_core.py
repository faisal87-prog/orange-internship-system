from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse
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
    TaskAssignmentStatus,
    TaskDifficulty,
    TaskSource,
)
from services.weekly_score import calculate_overall_weekly_score


class BackendCoreTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            email="admin@test.com",
            username="admin_test",
            password="pass1234",
            full_name="Admin User",
            role=Role.ADMIN,
            is_staff=True,
        )
        self.mentor = User.objects.create_user(
            email="mentor@test.com",
            username="mentor_test",
            password="pass1234",
            full_name="Mentor User",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.mentor,
            department="Engineering",
            job_title="Lead",
        )
        self.other_mentor = User.objects.create_user(
            email="other@test.com",
            username="other_mentor",
            password="pass1234",
            full_name="Other Mentor",
            role=Role.MENTOR,
        )
        MentorProfile.objects.create(
            user=self.other_mentor,
            department="Design",
            job_title="Lead",
        )
        self.program = InternshipProgram.objects.create(
            mentor=self.mentor,
            title="Test Program",
            description="Desc",
            role="Intern",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=60),
            duration_weeks=8,
            department="Engineering",
            weekly_hours=30,
            maximum_interns=3,
            status=ProgramStatus.ACTIVE,
        )
        self.intern_user = User.objects.create_user(
            email="intern@test.com",
            username="intern_test",
            password="pass1234",
            full_name="Intern User",
            role=Role.INTERN,
        )
        self.intern = InternProfile.objects.create(
            user=self.intern_user,
            mentor=self.mentor,
            program=self.program,
            learning_goals="Learn",
        )
        self.other_intern_user = User.objects.create_user(
            email="intern2@test.com",
            username="intern2_test",
            password="pass1234",
            full_name="Intern Two",
            role=Role.INTERN,
        )
        self.other_intern = InternProfile.objects.create(
            user=self.other_intern_user,
            mentor=self.other_mentor,
            learning_goals="Other",
        )
        self.week = RoadmapWeek.objects.create(
            roadmap=Roadmap.objects.create(
                program=self.program,
                title="Roadmap",
                summary="Summary",
                number_of_weeks=1,
            ),
            week_number=1,
            weekly_focus="Focus",
            display_order=1,
        )
        self.task = Task.objects.create(
            roadmap_week=self.week,
            program=self.program,
            created_by=self.mentor,
            title="Task A",
            description="Do work",
            difficulty=TaskDifficulty.EASY,
            estimated_time_minutes=120,
            due_date=date.today() - timedelta(days=1),
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
        )
        self.assignment = TaskAssignment.objects.create(
            task=self.task,
            intern=self.intern,
            status=TaskAssignmentStatus.TO_DO,
        )

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def test_login_returns_jwt(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "mentor@test.com", "password": "pass1234"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["user"]["role"], Role.MENTOR)

    def test_admin_can_create_mentor(self):
        self.auth(self.admin)
        response = self.client.post(
            "/api/accounts/mentors/create/",
            {
                "full_name": "New Mentor",
                "email": "new.mentor@test.com",
                "username": "new_mentor",
                "password": "SecurePass!234",
                "phone_number": "123",
                "department": "QA",
                "job_title": "Mentor",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="new.mentor@test.com", role=Role.MENTOR).exists())

    def test_create_mentor_rejects_duplicate_username_and_email(self):
        self.auth(self.admin)
        duplicate_username = self.client.post(
            "/api/accounts/mentors/create/",
            {
                "full_name": "Dup User",
                "email": "unique.mentor@test.com",
                "username": self.mentor.username,
                "password": "SecurePass!234",
                "phone_number": "123",
                "department": "QA",
                "job_title": "Mentor",
            },
            format="json",
        )
        self.assertEqual(duplicate_username.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            duplicate_username.data["username"][0],
            "This username is already in use.",
        )

        duplicate_email = self.client.post(
            "/api/accounts/mentors/create/",
            {
                "full_name": "Dup User",
                "email": self.mentor.email,
                "username": "brand_new_mentor",
                "password": "SecurePass!234",
                "phone_number": "123",
                "department": "QA",
                "job_title": "Mentor",
            },
            format="json",
        )
        self.assertEqual(duplicate_email.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            duplicate_email.data["email"][0],
            "This email is already in use.",
        )

    def test_mentor_program_ownership(self):
        self.auth(self.other_mentor)
        response = self.client.get(f"/api/programs/{self.program.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.auth(self.mentor)
        response = self.client.get(f"/api/programs/{self.program.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_cannot_edit_program(self):
        self.auth(self.admin)
        response = self.client.patch(
            f"/api/programs/{self.program.id}/",
            {"title": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_task_assignment_and_score_validation(self):
        self.auth(self.mentor)
        response = self.client.patch(
            f"/api/tasks/assignments/{self.assignment.id}/",
            {"score": 150, "status": TaskAssignmentStatus.COMPLETED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.patch(
            f"/api/tasks/assignments/{self.assignment.id}/",
            {"score": 90, "status": TaskAssignmentStatus.COMPLETED, "mentor_feedback": "Good"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.score, 90)

    def test_needs_revision_allows_missing_score(self):
        self.auth(self.mentor)
        response = self.client.patch(
            f"/api/tasks/assignments/{self.assignment.id}/",
            {
                "status": TaskAssignmentStatus.NEEDS_REVISION,
                "mentor_feedback": "Please revise the write-up.",
                "score": None,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, TaskAssignmentStatus.NEEDS_REVISION)
        self.assertIsNone(self.assignment.score)

    def test_completed_requires_score(self):
        self.auth(self.mentor)
        response = self.client.patch(
            f"/api/tasks/assignments/{self.assignment.id}/",
            {
                "status": TaskAssignmentStatus.COMPLETED,
                "mentor_feedback": "Done",
                "score": None,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("score", response.data)

        response = self.client.patch(
            f"/api/tasks/assignments/{self.assignment.id}/",
            {
                "status": TaskAssignmentStatus.COMPLETED,
                "mentor_feedback": "Done",
                "score": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.score, 0)
        self.assertEqual(self.assignment.status, TaskAssignmentStatus.COMPLETED)

    def test_task_resource_retains_file_and_external_link(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.auth(self.mentor)
        upload = SimpleUploadedFile(
            "guide.pdf",
            b"%PDF-1.4 sample",
            content_type="application/pdf",
        )
        response = self.client.post(
            "/api/tasks/resources/",
            {
                "task": self.task.id,
                "title": "Guide with link",
                "external_url": "https://example.com/extra",
                "file": upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data.get("file_url"))
        self.assertEqual(response.data.get("external_url"), "https://example.com/extra")

    def test_submission_versioning(self):
        self.auth(self.intern_user)
        for expected_version in (1, 2):
            response = self.client.post(
                "/api/submissions/",
                {
                    "task_assignment": self.assignment.id,
                    "written_response": f"Attempt {expected_version}",
                },
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data["version_number"], expected_version)
        self.assertEqual(Submission.objects.filter(task_assignment=self.assignment).count(), 2)

    def test_program_material_accepts_link_only_and_infers_type(self):
        self.auth(self.mentor)
        response = self.client.post(
            "/api/programs/materials/items/",
            {
                "program": self.program.id,
                "title": "Style guide",
                "external_url": "https://example.com/guide",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["resource_type"], "LINK")
        self.assertEqual(response.data["external_url"], "https://example.com/guide")

    def test_program_material_requires_file_or_link(self):
        self.auth(self.mentor)
        response = self.client.post(
            "/api/programs/materials/items/",
            {
                "program": self.program.id,
                "title": "Missing both",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Please provide a file or an external link.",
            str(response.data),
        )

    def test_task_resource_accepts_link_only(self):
        self.auth(self.mentor)
        response = self.client.post(
            "/api/tasks/resources/",
            {
                "task": self.task.id,
                "title": "Docs",
                "external_url": "https://docs.example.com",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["resource_type"], "LINK")

    def test_roadmap_includes_week_tasks_without_assignment_filter(self):
        ai_task = Task.objects.create(
            roadmap_week=self.week,
            program=self.program,
            created_by=self.mentor,
            title="AI Task",
            description="Generated",
            difficulty=TaskDifficulty.EASY,
            estimated_time_minutes=30,
            due_date=date.today(),
            requirement_type=RequirementType.OPTIONAL,
            source=TaskSource.AI_GENERATED,
        )
        self.auth(self.mentor)
        response = self.client.get(f"/api/roadmaps/{self.week.roadmap_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        weeks = response.data["weeks"]
        self.assertEqual(len(weeks), 1)
        task_ids = {task["id"] for task in weeks[0]["tasks"]}
        self.assertIn(self.task.id, task_ids)
        self.assertIn(ai_task.id, task_ids)
        self.assertEqual(len(weeks[0]["tasks"]), 2)

    def test_weekly_score_calculation(self):
        TaskAssignment.objects.filter(id=self.assignment.id).update(score=80)
        task_b = Task.objects.create(
            roadmap_week=self.week,
            program=self.program,
            created_by=self.mentor,
            title="Task B",
            description="More work",
            difficulty=TaskDifficulty.MEDIUM,
            estimated_time_minutes=60,
            due_date=date.today(),
            requirement_type=RequirementType.REQUIRED,
            source=TaskSource.MANUAL,
        )
        TaskAssignment.objects.create(task=task_b, intern=self.intern, score=100)
        score = calculate_overall_weekly_score(self.intern, self.week)
        self.assertEqual(score, 90)

        empty = calculate_overall_weekly_score(self.other_intern, self.week)
        self.assertIsNone(empty)

    def test_approved_report_visibility(self):
        report = WeeklyReport.objects.create(
            intern=self.intern,
            program=self.program,
            roadmap_week=self.week,
            performance_summary="Draft",
            status=AiContentStatus.DRAFT,
        )
        self.auth(self.intern_user)
        response = self.client.get(f"/api/reports/weekly/{report.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        report.status = AiContentStatus.APPROVED
        report.save(update_fields=["status"])
        response = self.client.get(f"/api/reports/weekly/{report.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_intern_data_isolation(self):
        other_assignment = TaskAssignment.objects.create(
            task=self.task,
            intern=self.other_intern,
        )
        self.auth(self.intern_user)
        response = self.client.get(f"/api/tasks/assignments/{other_assignment.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
