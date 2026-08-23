"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import {
  approveWeeklyReport,
  downloadWeeklyReportPdf,
  getWeeklyReport,
  updateWeeklyReport,
} from "@/lib/api/reports";
import { formatScoreOutOf100 } from "@/lib/weeklyScore";
import { fullName } from "@/lib/names";
import type { AiContentStatus, WeeklyReport } from "@/types";

type ReportDetail = WeeklyReport & { overallWeeklyScore?: number | null };

export default function WeeklyReportDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [status, setStatus] = useState<AiContentStatus>("DRAFT");
  const [internName, setInternName] = useState("Intern");
  const [summary, setSummary] = useState("");
  const [achievements, setAchievements] = useState("");
  const [learningProgress, setLearningProgress] = useState("");
  const [productivityAnalysis, setProductivityAnalysis] = useState("");
  const [mentorFocusSuggestions, setMentorFocusSuggestions] = useState("");
  const [recommendedFocusNextWeek, setRecommendedFocusNextWeek] = useState("");
  const [mentorNotes, setMentorNotes] = useState("");
  const [overallScore, setOverallScore] = useState<number | null | undefined>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, interns] = await Promise.all([
        getWeeklyReport(params.id),
        listInternProfiles(),
      ]);
      setReport(detail);
      setStatus(detail.status);
      setSummary(detail.content.performanceSummary ?? "");
      setAchievements((detail.content.achievements || []).join("\n"));
      setLearningProgress(detail.content.learningProgress ?? "");
      setProductivityAnalysis(detail.content.productivityAnalysis ?? "");
      setMentorFocusSuggestions((detail.content.mentorFocusSuggestions || []).join("\n"));
      setRecommendedFocusNextWeek(detail.content.recommendedFocusNextWeek ?? "");
      setMentorNotes(detail.additionalMentorNotes ?? "");
      setOverallScore(detail.overallWeeklyScore);
      const intern = interns.find((ip) => ip.id === detail.internProfileId);
      setInternName(intern ? fullName(intern.user) : "Intern");
    } catch (err) {
      setError(getErrorMessage(err, "Could not load weekly report."));
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const editable = status === "DRAFT";

  function payloadFromForm() {
    return {
      performance_summary: summary,
      achievements: achievements
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      learning_progress: learningProgress,
      productivity_analysis: productivityAnalysis,
      mentor_focus_suggestions: mentorFocusSuggestions
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      recommended_next_focus: recommendedFocusNextWeek,
      additional_mentor_notes: mentorNotes,
    };
  }

  async function saveEdits() {
    if (!report) return;
    setBusy(true);
    setMessage("");
    try {
      const updated = await updateWeeklyReport(report.id, payloadFromForm());
      setReport(updated);
      setOverallScore(updated.overallWeeklyScore);
      setStatus(updated.status);
      setMessage("Edits saved.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not save edits."));
    } finally {
      setBusy(false);
    }
  }

  async function onApprove() {
    if (!report) return;
    setBusy(true);
    setMessage("");
    try {
      await updateWeeklyReport(report.id, payloadFromForm());
      const approved = await approveWeeklyReport(report.id);
      setReport({ ...report, ...approved });
      setStatus(approved.status);
      setMessage("Report approved. It is now visible to the intern.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not approve report."));
    } finally {
      setBusy(false);
    }
  }

  async function onDownload() {
    if (!report) return;
    setBusy(true);
    setMessage("");
    try {
      await downloadWeeklyReportPdf(report.id);
      setMessage("PDF download started.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not download PDF."));
    } finally {
      setBusy(false);
    }
  }

  function onRegenerate() {
    if (!report || status !== "DRAFT") {
      setMessage("Only draft weekly reports can be regenerated.");
      return;
    }
    const query = new URLSearchParams({
      programId: report.programId,
      internId: report.internProfileId,
    });
    router.push(`/mentor/weekly-reports/generate?${query.toString()}`);
  }

  if (loading) return <LoadingState label="Loading report…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!report) return <p>Report not found.</p>;

  return (
    <div>
      <PageHeader
        title={`Week ${report.weekNumber} report`}
        description={internName}
        actions={
          <>
            {status === "APPROVED" || status === "DRAFT" ? (
              <button
                type="button"
                className="btn-primary"
                onClick={() => void onDownload()}
                disabled={busy}
              >
                Download PDF
              </button>
            ) : null}
            <Link href="/mentor/weekly-reports" className="btn-secondary">Back</Link>
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
        {editable ? (
          <button type="button" className="btn-secondary" onClick={onRegenerate}>
            Regenerate
          </button>
        ) : null}
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
              Approve report
            </button>
          </>
        ) : null}
      </div>
      {message ? (
        <p className="mb-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</p>
      ) : null}

      <section className="mb-4 rounded-xl border border-brand/30 bg-brand-soft/70 p-4">
        <h2 className="section-title">Overall Weekly Score</h2>
        {typeof overallScore === "number" ? (
          <p className="mt-2 text-3xl font-bold text-brand-dark">
            {formatScoreOutOf100(overallScore)}
          </p>
        ) : (
          <p className="mt-2 text-sm text-ink-muted">
            No scored tasks available for this week.
          </p>
        )}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card space-y-3 p-5">
          <div>
            <label className="label" htmlFor="summary">Performance summary</label>
            <textarea
              id="summary"
              className="input"
              rows={4}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              disabled={!editable}
            />
          </div>
          <div>
            <label className="label" htmlFor="achievements">
              Achievements (one per line)
            </label>
            <textarea
              id="achievements"
              className="input"
              rows={3}
              value={achievements}
              onChange={(e) => setAchievements(e.target.value)}
              disabled={!editable}
            />
          </div>
          <div>
            <label className="label" htmlFor="learning">Learning progress</label>
            <textarea
              id="learning"
              className="input"
              rows={3}
              value={learningProgress}
              onChange={(e) => setLearningProgress(e.target.value)}
              disabled={!editable}
            />
          </div>
        </section>

        <section className="card space-y-3 p-5">
          <div>
            <label className="label" htmlFor="productivity">Productivity analysis</label>
            <textarea
              id="productivity"
              className="input"
              rows={3}
              value={productivityAnalysis}
              onChange={(e) => setProductivityAnalysis(e.target.value)}
              disabled={!editable}
            />
          </div>
          <div>
            <label className="label" htmlFor="mentorFocus">
              Mentor focus suggestions (one per line)
            </label>
            <textarea
              id="mentorFocus"
              className="input"
              rows={3}
              value={mentorFocusSuggestions}
              onChange={(e) => setMentorFocusSuggestions(e.target.value)}
              disabled={!editable}
            />
          </div>
          <div>
            <label className="label" htmlFor="nextWeek">Recommended focus next week</label>
            <textarea
              id="nextWeek"
              className="input"
              rows={3}
              value={recommendedFocusNextWeek}
              onChange={(e) => setRecommendedFocusNextWeek(e.target.value)}
              disabled={!editable}
            />
          </div>
          <div>
            <label className="label" htmlFor="mentorNotes">Additional Mentor Notes</label>
            <textarea
              id="mentorNotes"
              className="input"
              rows={4}
              value={mentorNotes}
              onChange={(e) => setMentorNotes(e.target.value)}
              disabled={!editable}
              placeholder="Add any extra comments or context for this week."
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
        </section>
      </div>
    </div>
  );
}
