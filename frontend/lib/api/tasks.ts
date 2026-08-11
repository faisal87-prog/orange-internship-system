import {
  adaptAssignment,
  adaptResource,
  adaptTask,
  taskToApiPayload,
} from "@/lib/api/adapters";
import { apiRequest, unwrapList } from "@/lib/api/client";
import type { LearningResource, Task, TaskAssignment } from "@/types";

export async function listTasks(): Promise<Task[]> {
  const data = await apiRequest("/api/tasks/");
  return unwrapList(data).map(adaptTask);
}

export async function getTask(id: string): Promise<Task> {
  const data = await apiRequest(`/api/tasks/${id}/`);
  return adaptTask(data);
}

export async function createTask(payload: Record<string, unknown>) {
  const data = await apiRequest("/api/tasks/", {
    method: "POST",
    body: taskToApiPayload(payload),
  });
  return adaptTask(data);
}

export async function updateTask(id: string, payload: Record<string, unknown>) {
  const data = await apiRequest(`/api/tasks/${id}/`, {
    method: "PATCH",
    body: taskToApiPayload(payload),
  });
  return adaptTask(data);
}

export async function deleteTask(id: string) {
  await apiRequest(`/api/tasks/${id}/`, { method: "DELETE" });
}

export async function listAssignments(): Promise<TaskAssignment[]> {
  const data = await apiRequest("/api/tasks/assignments/");
  return unwrapList(data).map(adaptAssignment);
}

export async function getAssignment(id: string): Promise<{
  assignment: TaskAssignment;
  task: Task | null;
  raw: any;
}> {
  const raw = await apiRequest<any>(`/api/tasks/assignments/${id}/`);
  return {
    assignment: adaptAssignment(raw),
    task: raw.task ? adaptTask(raw.task) : null,
    raw,
  };
}

export async function updateAssignment(
  id: string,
  payload: Record<string, unknown>,
) {
  const data = await apiRequest(`/api/tasks/assignments/${id}/`, {
    method: "PATCH",
    body: payload,
  });
  return adaptAssignment(data);
}

export async function listTaskResources(taskId?: string): Promise<LearningResource[]> {
  const data = await apiRequest("/api/tasks/resources/");
  const items = unwrapList(data).map(adaptResource);
  if (!taskId) return items;
  // Filter by matching task from raw list when needed
  const raw = unwrapList(data) as any[];
  return raw
    .filter((item) => String(item.task) === String(taskId))
    .map(adaptResource);
}

export async function createTaskResource(payload: {
  task: number;
  title: string;
  external_url?: string;
  file?: File | null;
}) {
  const form = new FormData();
  form.append("task", String(payload.task));
  form.append("title", payload.title);
  if (payload.external_url) form.append("external_url", payload.external_url);
  if (payload.file) form.append("file", payload.file);
  const data = await apiRequest("/api/tasks/resources/", {
    method: "POST",
    formData: form,
  });
  return adaptResource(data);
}

export async function deleteTaskResource(id: string) {
  await apiRequest(`/api/tasks/resources/${id}/`, { method: "DELETE" });
}
