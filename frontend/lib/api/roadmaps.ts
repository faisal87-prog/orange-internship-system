import { adaptRoadmap, adaptRoadmapWeek } from "@/lib/api/adapters";
import { apiRequest, unwrapList } from "@/lib/api/client";
import type { Roadmap, RoadmapWeek } from "@/types";

export async function listRoadmaps(): Promise<Roadmap[]> {
  const data = await apiRequest("/api/roadmaps/");
  return unwrapList(data).map(adaptRoadmap);
}

export async function getRoadmap(id: string): Promise<Roadmap> {
  const data = await apiRequest(`/api/roadmaps/${id}/`);
  return adaptRoadmap(data);
}

export async function generateRoadmap(payload: {
  program_id: number;
  assignment_scope: string;
  selected_intern_ids?: number[];
}) {
  const data = await apiRequest("/api/roadmaps/generate/", {
    method: "POST",
    body: payload,
  });
  return adaptRoadmap(data);
}

export async function createRoadmap(payload: {
  program: number;
  title: string;
  summary?: string;
  assignment_scope: string;
  number_of_weeks: number;
  assigned_intern_ids?: number[];
  generated_by_ai?: boolean;
}) {
  const data = await apiRequest("/api/roadmaps/", {
    method: "POST",
    body: payload,
  });
  return adaptRoadmap(data);
}

export async function updateRoadmap(id: string, payload: Record<string, unknown>) {
  const data = await apiRequest(`/api/roadmaps/${id}/`, {
    method: "PATCH",
    body: payload,
  });
  return adaptRoadmap(data);
}

export async function publishRoadmap(id: string) {
  const data = await apiRequest(`/api/roadmaps/${id}/publish/`, { method: "POST" });
  return adaptRoadmap(data);
}

export async function createRoadmapWeek(payload: {
  roadmap: number;
  week_number: number;
  weekly_focus: string;
  learning_objectives?: string[];
  expected_skills_gained?: string[];
  mentor_notes?: string;
  display_order?: number;
}) {
  const data = await apiRequest("/api/roadmaps/weeks/", {
    method: "POST",
    body: payload,
  });
  return adaptRoadmapWeek(data);
}

export async function updateRoadmapWeek(id: string, payload: Record<string, unknown>) {
  const data = await apiRequest(`/api/roadmaps/weeks/${id}/`, {
    method: "PATCH",
    body: payload,
  });
  return adaptRoadmapWeek(data);
}

export async function listRoadmapWeeks(): Promise<(RoadmapWeek & { id: string; roadmapId: string })[]> {
  const data = await apiRequest("/api/roadmaps/weeks/");
  return unwrapList(data).map((raw: any) => ({
    id: String(raw.id),
    roadmapId: String(raw.roadmap),
    ...adaptRoadmapWeek(raw),
  }));
}
