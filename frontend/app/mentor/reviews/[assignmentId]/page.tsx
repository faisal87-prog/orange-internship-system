"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import { listSubmissions } from "@/lib/api/submissions";
import { getAssignment, updateAssignment } from "@/lib/api/tasks";
import { fullName } from "@/lib/names";
import type { Submission, Task, TaskAssignment, TaskStatus } from "@/types";

export default function ReviewSubmissionPage() {
  const params = useParams<{ assignmentId: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assignment, setAssignment] = useState<TaskAssignment | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [internName, setInternName] = useState("Intern");
  const [latest, setLatest] = useState<Submission | null>(null);
  const [score, setScore] = useState("");
  const [feedback, setFeedback] = useState("");
  const [status, setStatus] = useState<TaskStatus>("COMPLETED");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [{ assignment: assign, task: nestedTask, raw }, submissions, interns] =
        await Promise.all([
          getAssignment(params.assignmentId),
          listSubmissions(params.assignmentId),
          listInternProfiles(),
        ]);
      setAssignment(assign);
      setTask(nestedTask);
      setScore(assign.score?.toString() ?? "");
      setFeedback(assign.mentorFeedback ?? "");
      setStatus(
        assign.status === "NEEDS_REVISION" || assign.status === "COMPLETED"
          ? assign.status
          : "COMPLETED",
      );
      const intern = interns.find((ip) => ip.id === assign.internProfileId);
      setInternName(intern ? fullName(intern.user) : raw.intern_name || "Intern");
      const sorted = submissions
        .slice()
        .sort((a, b) => b.submissionVersion - a.submissionVersion);
      setLatest(sorted[0] ?? null);
    } catch (err) {
      setError(getErrorMessage(err, "Could not load submission."));
    } finally {
      setLoading(false);
    }
  }, [params.assignmentId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!assignment) return;
    if (status !== "COMPLETED" && status !== "NEEDS_REVISION") {
      setMessage("Outcome must be Completed or Needs revision.");
      return;
    }

    const trimmedScore = score.trim();
    const payload: Record<string, unknown> = {
      mentor_feedback: feedback,
      status,
    };

    if (status === "COMPLETED") {
      const parsed = Number(trimmedScore);
      if (
        trimmedScore === "" ||
        !Number.isInteger(parsed) ||
        parsed < 0 ||
        parsed > 100
      ) {
        setMessage("Score must be an integer between 0 and 100.");
        return;
      }
      payload.score = parsed;
    } else if (trimmedScore === "") {
      payload.score = null;
    } else {
      const parsed = Number(trimmedScore);
      if (!Number.isInteger(parsed) || parsed < 0 || parsed > 100) {
        setMessage("Score must be an integer between 0 and 100.");
        return;
      }
      payload.score = parsed;
    }

    setSaving(true);
    setMessage("");
    try {
      const updated = await updateAssignment(assignment.id, payload);
      setAssignment(updated);
      setScore(updated.score?.toString() ?? "");
      const scoreText =
        typeof updated.score === "number" ? ` Score ${updated.score}/100.` : "";
      setMessage(`Review saved. Status set to ${status}.${scoreText}`);
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not save review."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <LoadingState label="Loading review…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!assignment) return <p>Assignment not found.</p>;

  return (
    <div>
      <PageHeader
        title="Review submission"
        description={`${task?.title ?? "Task"} · ${internName}`}
        actions={<Link href="/mentor/reviews" className="btn-secondary">Back</Link>}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card space-y-3 p-5">
          <div className="flex items-center gap-2">
            <StatusBadge kind="task" value={assignment.status} />
            <span className="text-sm text-ink-muted">
              Latest version {latest?.submissionVersion ?? "—"}
            </span>
          </div>
          <div>
            <h2 className="font-semibold text-ink">Written response</h2>
            <p className="mt-1 text-sm text-ink-muted">
              {latest?.writtenResponse || "No written response"}
            </p>
          </div>
          <div>
            <h2 className="font-semibold text-ink">Files</h2>
            {latest?.files?.length ? (
              <ul className="mt-1 space-y-1 text-sm">
                {latest.files.map((file) => (
                  <li key={file.id || file.name}>
                    {file.url ? (
                      <a
                        href={file.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand underline"
                      >
                        {file.name}
                      </a>
                    ) : (
                      <span className="text-ink-muted">{file.name}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-ink-muted">None</p>
            )}
          </div>
          <div>
            <h2 className="font-semibold text-ink">External link</h2>
            {latest?.externalLink ? (
              <a
                href={latest.externalLink}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-block text-sm text-brand underline"
              >
                {latest.externalLink}
              </a>
            ) : (
              <p className="mt-1 text-sm text-ink-muted">None</p>
            )}
          </div>
          {latest?.internNotes ? (
            <div>
              <h2 className="font-semibold text-ink">Intern notes</h2>
              <p className="mt-1 text-sm text-ink-muted">{latest.internNotes}</p>
            </div>
          ) : null}
        </section>

        <form onSubmit={onSubmit} className="card space-y-4 p-5">
          <div>
            <label className="label" htmlFor="feedback">Mentor feedback</label>
            <textarea
              id="feedback"
              className="input"
              rows={4}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="label" htmlFor="score">
              Score (0–100{status === "COMPLETED" ? ", required" : ", optional"})
            </label>
            <input
              id="score"
              type="number"
              min={0}
              max={100}
              step={1}
              className="input"
              value={score}
              onChange={(e) => setScore(e.target.value)}
              required={status === "COMPLETED"}
            />
          </div>
          <div>
            <label className="label" htmlFor="status">Outcome status</label>
            <select
              id="status"
              className="input"
              value={status}
              onChange={(e) => setStatus(e.target.value as TaskStatus)}
            >
              <option value="COMPLETED">Completed</option>
              <option value="NEEDS_REVISION">Needs revision</option>
            </select>
          </div>
          {message ? (
            <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">
              {message}
            </p>
          ) : null}
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Save review"}
          </button>
        </form>
      </div>
    </div>
  );
}
