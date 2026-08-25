"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { WeeklyPerformanceComparisonTable } from "@/components/reports/WeeklyPerformanceComparisonTable";
import type { PerformanceComparison } from "@/components/reports/WeeklyPerformanceComparisonTable";
import { WeeklyScoreCard } from "@/components/reports/WeeklyScoreCard";
import { DownloadPdfButton } from "@/components/resources/DownloadPdfButton";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api/errors";
import { downloadWeeklyReportPdf, getWeeklyReport } from "@/lib/api/reports";
import { getInternContext, type InternContext } from "@/lib/intern";
import type { WeeklyTaskScore } from "@/lib/weeklyScore";

export default function InternReportDetailPage() {
  const params = useParams<{ id: string }>();
  const { user } = useAuth();
  const [ctx, setCtx] = useState<InternContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [comparison, setComparison] = useState<PerformanceComparison | null>(null);

  const load = useCallback(async () => {
    if (!user) {
      setCtx(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const nextCtx = await getInternContext(user.id);
      setCtx(nextCtx);
      const found = nextCtx?.approvedReports.find((r) => r.id === params.id);
      if (found) {
        const detail = await getWeeklyReport(found.id);
        setComparison(detail.performanceComparison ?? null);
      } else {
        setComparison(null);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Unable to load report."));
    } finally {
      setLoading(false);
    }
  }, [params.id, user]);

  useEffect(() => {
    void load();
  }, [load]);

  const report = ctx?.approvedReports.find((r) => r.id === params.id);

  const scores = useMemo<WeeklyTaskScore[]>(() => {
    if (!report || !ctx) return [];
    return ctx.myTasks
      .filter(
        (row) =>
          row.task.weekNumber === report.weekNumber &&
          typeof row.assignment.score === "number",
      )
      .map((row) => ({
        taskTitle: row.task.title,
        score: row.assignment.score as number,
      }));
  }, [ctx, report]);

  if (loading) return <LoadingState label="Loading report…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  if (!report) {
    return (
      <div className="card p-6">
        <p className="font-semibold">Report unavailable</p>
        <p className="mt-2 text-sm text-ink-muted">
          Draft or other interns’ reports are not visible.
        </p>
        <Link href="/intern/reports" className="btn-secondary mt-4 inline-flex">
          Back
        </Link>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={`Week ${report.weekNumber} performance report`}
        description="Approved by your mentor"
        actions={
          <>
            <DownloadPdfButton
              fileName={`week-${report.weekNumber}-report.pdf`}
              label="Download PDF"
              onClick={() => downloadWeeklyReportPdf(report.id)}
            />
            <Link href="/intern/reports" className="btn-secondary">Back</Link>
          </>
        }
      />

      <div className="mb-4">
        <WeeklyScoreCard scores={scores} />
      </div>

      <div className="mb-4">
        <WeeklyPerformanceComparisonTable comparison={comparison} />
      </div>

      <div className="card space-y-4 p-6 text-sm">
        <div>
          <h2 className="font-semibold">Performance summary</h2>
          <p className="text-ink-muted">{report.content.performanceSummary}</p>
        </div>
        <div>
          <h2 className="font-semibold">Achievements</h2>
          <ul className="list-disc pl-5 text-ink-muted">
            {(report.content.achievements || []).map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold">Learning progress</h2>
          <p className="text-ink-muted">{report.content.learningProgress}</p>
        </div>
        <div>
          <h2 className="font-semibold">Productivity analysis</h2>
          <p className="text-ink-muted">{report.content.productivityAnalysis}</p>
        </div>
        <div>
          <h2 className="font-semibold">Mentor focus suggestions</h2>
          <ul className="list-disc pl-5 text-ink-muted">
            {(report.content.mentorFocusSuggestions || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-semibold">Recommended focus next week</h2>
          <p className="text-ink-muted">{report.content.recommendedFocusNextWeek}</p>
        </div>
        {report.additionalMentorNotes ? (
          <div>
            <h2 className="font-semibold">Additional Mentor Notes</h2>
            <p className="text-ink-muted">{report.additionalMentorNotes}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
