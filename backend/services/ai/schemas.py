"""Pydantic schemas for AI Prompt Builder and Roadmap Generator structured outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GeneratedRoadmapPrompt(BaseModel):
    prompt_title: str
    roadmap_generation_prompt: str
    important_constraints: list[str] = Field(default_factory=list)
    personalization_points: list[str] = Field(default_factory=list)
    missing_context_notes: list[str] = Field(default_factory=list)


class GeneratedTask(BaseModel):
    title: str
    description: str
    difficulty: Literal["EASY", "MEDIUM", "HARD"]
    estimated_time_minutes: int
    deliverable: str
    success_criteria: str
    due_date: str
    requirement_type: Literal["REQUIRED", "OPTIONAL"]


class GeneratedWeek(BaseModel):
    week_number: int
    weekly_focus: str
    learning_objectives: list[str]
    expected_skills_gained: list[str]
    mentor_notes: str = ""
    tasks: list[GeneratedTask]


class GeneratedRoadmap(BaseModel):
    title: str
    summary: str
    number_of_weeks: int
    weeks: list[GeneratedWeek]


class GeneratedWeeklyReportPrompt(BaseModel):
    prompt_title: str
    weekly_report_generation_prompt: str
    important_constraints: list[str] = Field(default_factory=list)
    personalization_points: list[str] = Field(default_factory=list)
    missing_context_notes: list[str] = Field(default_factory=list)


class GeneratedWeeklyReport(BaseModel):
    performance_summary: str
    achievements: str
    learning_progress: str
    productivity_analysis: str
    mentor_focus_suggestions: str
    recommended_next_focus: str
