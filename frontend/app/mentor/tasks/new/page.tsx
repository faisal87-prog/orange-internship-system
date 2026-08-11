"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { InternChipPicker } from "@/components/interns/InternChips";
import {
  PendingLearningResource,
  ResourceManager,
} from "@/components/resources/ResourceManager";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import { listPrograms } from "@/lib/api/programs";
import { createTask, createTaskResource } from "@/lib/api/tasks";
import { fullName } from "@/lib/names";
import type { InternshipProgram } from "@/types";

export default function CreateTaskPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [myPrograms, setMyPrograms] = useState<InternshipProgram[]>([]);
  const [internOptions, setInternOptions] = useState<{ id: string; name: string }[]>([]);
  const [selectedInternIds, setSelectedInternIds] = useState<string[]>([]);
  const [resources, setResources] = useState<PendingLearningResource[]>([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [programs, ips] = await Promise.all([listPrograms(), listInternProfiles()]);
      setMyPrograms(programs.filter((p) => p.mentorId === user?.id));
      setInternOptions(
        ips
          .filter((ip) => ip.mentorId === user?.id)
          .map((ip) => ({ id: ip.id, name: fullName(ip.user) || ip.id })),
      );
    } catch (err) {
      setError(getErrorMessage(err, "Could not load form data."));
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const options = useMemo(() => internOptions, [internOptions]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedInternIds.length) {
      setMessage("Select at least one intern.");
      return;
    }
    setSaving(true);
    setMessage("");
    const form = new FormData(e.currentTarget);
    try {
      const task = await createTask({
        programId: String(form.get("programId") || ""),
        title: String(form.get("title") || ""),
        description: String(form.get("description") || ""),
        difficulty: String(form.get("difficulty") || "EASY"),
        estimatedTime: String(form.get("estimatedTime") || "1 hour"),
        dueDate: String(form.get("deadline") || ""),
        requirementType: String(form.get("requirementType") || "REQUIRED"),
        deliverable: String(form.get("deliverable") || ""),
        successCriteria: String(form.get("successCriteria") || ""),
        assignInternIds: selectedInternIds,
        source: "MANUAL",
      });

      for (const resource of resources) {
        await createTaskResource({
          task: Number(task.id),
          title: resource.title,
          external_url:
            resource.externalUrl ||
            (resource.kind === "LINK" || resource.href?.startsWith("http")
              ? resource.href
              : undefined),
          file: resource.file ?? null,
        });
      }

      setMessage(
        `Task created with ${resources.length} resource(s) and ${selectedInternIds.length} assignment(s).`,
      );
      router.push("/mentor/tasks");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not create task."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState label="Loading…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="Create task manually"
        description="Mentors can create tasks, attach learning resources, and assign one task to multiple interns."
        actions={<Link href="/mentor/tasks" className="btn-secondary">Cancel</Link>}
      />
      <form onSubmit={onSubmit} className="card mx-auto max-w-3xl space-y-4 p-6">
        <div>
          <label className="label" htmlFor="programId">Program</label>
          <select id="programId" name="programId" className="input" required>
            {myPrograms.map((p) => (
              <option key={p.id} value={p.id}>{p.title}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="title">Title</label>
          <input id="title" name="title" className="input" required />
        </div>
        <div>
          <label className="label" htmlFor="description">Description</label>
          <textarea
            id="description"
            name="description"
            className="input"
            rows={5}
            required
            placeholder="Detailed explanation of what the intern is expected to complete."
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="difficulty">Difficulty</label>
            <input id="difficulty" name="difficulty" className="input" />
          </div>
          <div>
            <label className="label" htmlFor="estimatedTime">Estimated time</label>
            <input id="estimatedTime" name="estimatedTime" className="input" />
          </div>
          <div>
            <label className="label" htmlFor="deadline">Due date</label>
            <input id="deadline" name="deadline" type="date" className="input" required />
          </div>
          <div>
            <label className="label" htmlFor="requirementType">Required or optional</label>
            <select id="requirementType" name="requirementType" className="input" defaultValue="REQUIRED">
              <option value="REQUIRED">Required</option>
              <option value="OPTIONAL">Optional</option>
            </select>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="deliverable">Deliverables</label>
          <input id="deliverable" name="deliverable" className="input" />
        </div>
        <div>
          <label className="label" htmlFor="successCriteria">Success criteria</label>
          <textarea id="successCriteria" name="successCriteria" className="input" rows={2} />
        </div>

        <InternChipPicker
          options={options}
          selectedIds={selectedInternIds}
          onChange={setSelectedInternIds}
          label="Assign interns"
        />

        <div className="border-t border-line pt-4">
          <ResourceManager resources={resources} onChange={setResources} />
        </div>

        {message ? (
          <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>
        ) : null}
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Creating…" : "Create and assign"}
        </button>
      </form>
    </div>
  );
}
