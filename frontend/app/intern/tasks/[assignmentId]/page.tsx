"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { TaskDetailsPanel } from "@/components/tasks/TaskDetailsPanel";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api/errors";
import { createSubmission } from "@/lib/api/submissions";
import { updateAssignment } from "@/lib/api/tasks";
import { getInternContext, type InternContext } from "@/lib/intern";
import { formatDateTime } from "@/lib/labels";
import type { Submission, TaskStatus } from "@/types";

const ALLOWED = "PDF, DOC, DOCX, PPT, PPTX, PNG, JPG, JPEG, TXT, CSV, ZIP · max 20 MB each";

const transitions: Record<TaskStatus, TaskStatus[]> = {
  TO_DO: ["IN_PROGRESS"],
  IN_PROGRESS: ["SUBMITTED"],
  SUBMITTED: [],
  NEEDS_REVISION: ["IN_PROGRESS", "SUBMITTED"],
  COMPLETED: [],
};

export default function InternTaskDetailPage() {
  const params = useParams<{ assignmentId: string }>();
  const { user } = useAuth();
  const [ctx, setCtx] = useState<InternContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus | undefined>();
  const [subs, setSubs] = useState<Submission[]>([]);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!user) {
      setCtx(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await getInternContext(user.id);
      setCtx(data);
      const row = data?.myTasks.find((item) => item.assignment.id === params.assignmentId);
      setStatus(row?.assignment.status);
      setSubs(
        data?.mySubmissions.filter((s) => s.taskAssignmentId === params.assignmentId) ?? [],
      );
    } catch (err) {
      setError(getErrorMessage(err, "Unable to load task."));
    } finally {
      setLoading(false);
    }
  }, [params.assignmentId, user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading task…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  const row = ctx?.myTasks.find((item) => item.assignment.id === params.assignmentId);

  if (!row || !status) {
    return <p>Task assignment not found for this intern.</p>;
  }

  const { assignment, task } = row;
  const nextStatuses = transitions[status];

  async function onStatusChange(next: TaskStatus) {
    setMessage("");
    try {
      const updated = await updateAssignment(assignment.id, { status: next });
      setStatus(updated.status);
      setMessage(`Status updated to ${updated.status}.`);
    } catch (err) {
      setMessage(getErrorMessage(err, "Unable to update status."));
    }
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const form = new FormData(formEl);
    const writtenResponse = String(form.get("writtenResponse") || "");
    const externalLink = String(form.get("externalLink") || "");
    const internNotes = String(form.get("internNotes") || "");
    const fileList = form.getAll("files").filter((f) => f instanceof File && f.name) as File[];
    if (!writtenResponse && fileList.length === 0 && !externalLink) {
      setMessage("Add a written response, at least one file, or an external link.");
      return;
    }
    try {
      const created = await createSubmission({
        task_assignment: Number(assignment.id),
        written_response: writtenResponse || undefined,
        external_url: externalLink || undefined,
        intern_notes: internNotes || undefined,
        files: fileList,
      });
      setSubs((prev) => [...prev, created]);
      setStatus("SUBMITTED");
      setMessage(`Submission version ${created.submissionVersion} saved.`);
      formEl.reset();
    } catch (err) {
      setMessage(getErrorMessage(err, "Unable to submit work."));
    }
  }

  return (
    <div>
      <PageHeader
        title={task.title}
        description={`Week ${task.weekNumber} · ${task.requirementType === "REQUIRED" ? "Required" : "Optional"} task`}
        actions={<Link href="/intern/tasks" className="btn-secondary">Back to board</Link>}
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="card space-y-4 p-5 lg:col-span-2">
          <StatusBadge kind="task" value={status} />
          <TaskDetailsPanel
            task={task}
            dueDate={assignment.deadline}
            resources={task.resources}
          />
          {typeof assignment.score === "number" || assignment.mentorFeedback ? (
            <div className="rounded-xl bg-brand-soft p-3 text-sm">
              <p className="font-semibold text-ink">Mentor review</p>
              {typeof assignment.score === "number" ? (
                <p className="mt-1 text-ink-muted">Score: {assignment.score}/100</p>
              ) : null}
              {assignment.mentorFeedback ? (
                <p className="mt-1 text-ink-muted">{assignment.mentorFeedback}</p>
              ) : null}
            </div>
          ) : null}

          <div>
            <h2 className="font-semibold text-ink">Update status</h2>
            <div className="mt-2 flex flex-wrap gap-2">
              {nextStatuses.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  No intern status changes available from {status}.
                </p>
              ) : (
                nextStatuses.map((next) => (
                  <button
                    key={next}
                    type="button"
                    className="btn-secondary"
                    onClick={() => void onStatusChange(next)}
                  >
                    Mark as {next.split("_").join(" ")}
                  </button>
                ))
              )}
            </div>
          </div>
        </section>

        <section className="card p-5">
          <h2 className="section-title">Submit work</h2>
          <p className="mt-2 text-xs text-ink-muted">{ALLOWED}</p>
          <form onSubmit={(e) => void onSubmit(e)} className="mt-4 space-y-3">
            <div>
              <label className="label" htmlFor="writtenResponse">Written response</label>
              <textarea id="writtenResponse" name="writtenResponse" className="input" rows={4} />
            </div>
            <div>
              <label className="label" htmlFor="files">Upload files (multiple)</label>
              <input id="files" name="files" type="file" multiple className="input" />
            </div>
            <div>
              <label className="label" htmlFor="externalLink">External link (optional)</label>
              <input id="externalLink" name="externalLink" type="url" className="input" />
            </div>
            <div>
              <label className="label" htmlFor="internNotes">Intern notes</label>
              <textarea id="internNotes" name="internNotes" className="input" rows={2} />
            </div>
            <button type="submit" className="btn-primary w-full">
              Submit version
            </button>
          </form>
          {message ? <p className="mt-3 text-sm text-emerald-700">{message}</p> : null}
        </section>
      </div>

      <section className="card mt-6 p-5">
        <h2 className="section-title">My submission versions</h2>
        <ul className="mt-4 space-y-3">
          {subs
            .slice()
            .sort((a, b) => b.submissionVersion - a.submissionVersion)
            .map((sub) => (
              <li key={sub.id} className="rounded-xl border border-line p-3 text-sm">
                <p className="font-semibold">Version {sub.submissionVersion}</p>
                <p className="mt-1 text-ink-muted">{sub.writtenResponse || "No written response"}</p>
                <div className="mt-2 space-y-1 text-xs text-ink-muted">
                  <p>{formatDateTime(sub.submittedAt)}</p>
                  <p>
                    Files:{" "}
                    {sub.files.length
                      ? sub.files.map((file, index) => (
                          <span key={file.id || `${sub.id}-file-${index}`}>
                            {index > 0 ? ", " : null}
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
                              file.name
                            )}
                          </span>
                        ))
                      : "None"}
                  </p>
                  {sub.externalLink ? (
                    <p>
                      Link:{" "}
                      <a
                        href={sub.externalLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand underline"
                      >
                        {sub.externalLink}
                      </a>
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          {subs.length === 0 ? <li className="text-ink-muted">No submissions yet.</li> : null}
        </ul>
      </section>
    </div>
  );
}
