"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { FinalSummaryContent } from "@/components/final-summary/FinalSummaryContent";
import { InternshipWeekPerformanceTable } from "@/components/final-summary/InternshipWeekPerformanceTable";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import {
  approveFinalSummary,
  downloadFinalSummaryPdf,
  getFinalSummary,
  updateFinalSummary,
} from "@/lib/api/reports";
import { fullName } from "@/lib/names";
import { formatFinalScoreLabel } from "@/lib/weeklyScore";
import type { AiContentStatus, FinalSummary } from "@/types";

export default function FinalSummaryDetailPage() {
  const params = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<FinalSummary | null>(null);
  const [status, setStatus] = useState<AiContentStatus>("DRAFT");
  const [content, setContent] = useState<FinalSummary["content"] | null>(null);
  const [comments, setComments] = useState("");
  const [mentorNotes, setMentorNotes] = useState("");
  const [internName, setInternName] = useState("Intern");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, interns] = await Promise.all([
        getFinalSummary(params.id),
        listInternProfiles(),
      ]);
      setSummary(detail);
      setStatus(detail.status);
      setContent(detail.content);
      setComments(detail.mentorFinalComments ?? "");
      setMentorNotes(detail.additionalMentorNotes ?? "");
      const intern = interns.find((ip) => ip.id === detail.internProfileId);
      setInternName(intern ? fullName(intern.user) : "Intern");
    } catch (err) {
      setError(getErrorMessage(err, "Could not load final summary."));
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const editable = status === "DRAFT";
  const scoreLabel = formatFinalScoreLabel(
    summary?.mentorFinalScore,
    summary?.scoredWeeklyReportCount,
  );

  async function saveEdits() {
    if (!summary || !content) return;
    setBusy(true);
    setMessage("");
    try {
      const updated = await updateFinalSummary(summary.id, {
        overall_performance_summary: content.overallPerformanceSummary,
        learning_journey: content.learningJourney,
        main_achievements: content.mainAchievements,
        goal_achievement: content.goalAchievement,
        final_performance_summary: content.finalPerformanceSummary,
        mentor_comments: comments,
        additional_mentor_notes: mentorNotes,
      });
      setSummary(updated);
      setContent(updated.content);
      setStatus(updated.status);
      setComments(updated.mentorFinalComments ?? "");
      setMentorNotes(updated.additionalMentorNotes ?? "");
      setMessage("Edits saved.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not save edits."));
    } finally {
      setBusy(false);
    }
  }

  async function onApprove() {
    if (!summary || !content) return;
    setBusy(true);
    setMessage("");
    try {
      await updateFinalSummary(summary.id, {
        overall_performance_summary: content.overallPerformanceSummary,
        learning_journey: content.learningJourney,
        main_achievements: content.mainAchievements,
        goal_achievement: content.goalAchievement,
        final_performance_summary: content.finalPerformanceSummary,
        mentor_comments: comments,
        additional_mentor_notes: mentorNotes,
      });
      const approved = await approveFinalSummary(summary.id);
      setSummary(approved);
      setContent(approved.content);
      setStatus(approved.status);
      setMessage("Final summary approved and stored.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not approve summary."));
    } finally {
      setBusy(false);
    }
  }

  async function onDownload() {
    if (!summary) return;
    setBusy(true);
    setMessage("");
    try {
      await downloadFinalSummaryPdf(summary.id);
      setMessage("PDF download started.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not download PDF."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingState label="Loading summary…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!summary || !content) return <p>Final summary not found.</p>;

  return (
    <div>
      <PageHeader
        title="Final internship summary"
        description={internName}
        actions={
          <>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void onDownload()}
              disabled={busy}
            >
              Download PDF
            </button>
            <Link href="/mentor/final-summaries" className="btn-secondary">Back</Link>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <StatusBadge kind="ai" value={status} />
        {editable ? (
          <span className="rounded-full bg-brand-soft px-3 py-1 text-xs font-semibold text-brand-dark">
            Edit mode
          </span>
        ) : null}
        <button
          type="button"
          className="btn-secondary"
          onClick={() => {
            if (!summary) return;
            window.location.href = `/mentor/final-summaries/generate?programId=${summary.programId}&internId=${summary.internProfileId}`;
          }}
          disabled={!editable || busy}
        >
          Regenerate
        </button>
        {editable ? (
          <>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void saveEdits()}
              disabled={busy}
            >
              Save edits
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void onApprove()}
              disabled={busy}
            >
              Approve summary
            </button>
          </>
        ) : null}
      </div>
      {message ? (
        <p className="mb-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>
      ) : null}

      <div className="mb-4">
        <InternshipWeekPerformanceTable weekPerformance={summary.weekPerformance} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-5">
          <FinalSummaryContent
            content={content}
            editable={editable}
            onChange={setContent}
          />
        </section>

        <section className="card space-y-4 p-5">
          <div>
            <p className="label">Final Score</p>
            <p className="mt-1 text-sm font-medium text-ink">{scoreLabel.scoreText}</p>
            {scoreLabel.detail ? (
              <p className="mt-1 text-xs text-ink-muted">{scoreLabel.detail}</p>
            ) : null}
          </div>
          <div>
            <label className="label" htmlFor="comments">Mentor comments</label>
            <textarea
              id="comments"
              className="input"
              rows={4}
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              disabled={!editable}
            />
          </div>
          <div>
            <label className="label" htmlFor="mentorNotes">Additional Notes</label>
            <textarea
              id="mentorNotes"
              className="input"
              rows={4}
              value={mentorNotes}
              onChange={(e) => setMentorNotes(e.target.value)}
              disabled={!editable}
              placeholder="Add any extra comments or context."
            />
          </div>
          {editable ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void saveEdits()}
              disabled={busy}
            >
              Save edits
            </button>
          ) : null}
          <p className="text-xs text-ink-muted">
            Final Score is calculated automatically from approved weekly report scores.
            AI does not make hiring decisions.
          </p>
        </section>
      </div>
    </div>
  );
}
