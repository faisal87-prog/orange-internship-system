"use client";

import { useCallback, useEffect, useState } from "react";
import { FinalSummaryContent } from "@/components/final-summary/FinalSummaryContent";
import { InternshipWeekPerformanceTable } from "@/components/final-summary/InternshipWeekPerformanceTable";
import type { WeekPerformance } from "@/components/final-summary/InternshipWeekPerformanceTable";
import { InternshipWeeksCompletedTasksTable } from "@/components/final-summary/InternshipWeeksCompletedTasksTable";
import type { WeeksCompletedTasks } from "@/components/final-summary/InternshipWeeksCompletedTasksTable";
import { MentorSignatureBlock } from "@/components/final-summary/MentorSignatureBlock";
import { DownloadPdfButton } from "@/components/resources/DownloadPdfButton";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api/errors";
import { downloadFinalSummaryPdf, getFinalSummary } from "@/lib/api/reports";
import { getInternContext, type InternContext } from "@/lib/intern";
import { formatScoreOutOf100 } from "@/lib/weeklyScore";
import type { FinalSummary } from "@/types";

export default function InternFinalSummaryPage() {
  const { user } = useAuth();
  const [ctx, setCtx] = useState<InternContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [weekPerformance, setWeekPerformance] = useState<WeekPerformance | null>(null);
  const [weeksCompletedTasks, setWeeksCompletedTasks] =
    useState<WeeksCompletedTasks | null>(null);
  const [mentorName, setMentorName] = useState<string | undefined>();
  const [detailContent, setDetailContent] = useState<FinalSummary["content"] | null>(
    null,
  );

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
      if (nextCtx?.finalSummary) {
        const detail = await getFinalSummary(nextCtx.finalSummary.id);
        setDetailContent(detail.content);
        setWeekPerformance(
          detail.weekPerformance ?? nextCtx.finalSummary.weekPerformance ?? null,
        );
        setWeeksCompletedTasks(
          detail.weeksCompletedTasks ?? nextCtx.finalSummary.weeksCompletedTasks ?? null,
        );
        setMentorName(detail.mentorName ?? nextCtx.finalSummary.mentorName);
      } else {
        setDetailContent(null);
        setWeekPerformance(null);
        setWeeksCompletedTasks(null);
        setMentorName(undefined);
      }
    } catch (err) {
      setError(getErrorMessage(err, "Unable to load final summary."));
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading final summary…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  const summary = ctx?.finalSummary;
  const content = detailContent ?? summary?.content;

  return (
    <div>
      <PageHeader
        title="Final internship summary"
        description="Only an approved final summary is visible. Draft summaries remain hidden."
        actions={
          summary ? (
            <DownloadPdfButton
              fileName="final-internship-summary.pdf"
              label="Download PDF"
              onClick={() => downloadFinalSummaryPdf(summary.id)}
            />
          ) : undefined
        }
      />
      {!summary || !content ? (
        <EmptyState
          title="No approved final summary"
          description="When your mentor approves your final internship summary, you can view and download it here."
        />
      ) : (
        <div className="space-y-4">
          <section className="card p-6">
            <FinalSummaryContent content={content} sections="intro" />
          </section>
          <InternshipWeeksCompletedTasksTable
            weeksCompletedTasks={weeksCompletedTasks ?? summary.weeksCompletedTasks}
          />
          <InternshipWeekPerformanceTable
            weekPerformance={weekPerformance ?? summary.weekPerformance}
          />
          <section className="card space-y-4 p-6">
            <FinalSummaryContent content={content} sections="narrative" />
            <div className="text-sm">
              <h2 className="section-title text-brand-dark">Final Score</h2>
              <p className="mt-1 text-ink-muted">
                {typeof summary.mentorFinalScore === "number"
                  ? formatScoreOutOf100(summary.mentorFinalScore)
                  : "No scored weeks available."}
              </p>
            </div>
            {summary.mentorFinalComments ? (
              <div className="text-sm">
                <h2 className="section-title text-brand-dark">Mentor Comments</h2>
                <p className="mt-1 text-ink-muted">{summary.mentorFinalComments}</p>
              </div>
            ) : null}
            {summary.additionalMentorNotes ? (
              <div className="text-sm">
                <h2 className="section-title text-brand-dark">Additional Notes</h2>
                <p className="mt-1 text-ink-muted">{summary.additionalMentorNotes}</p>
              </div>
            ) : null}
          </section>
          <MentorSignatureBlock mentorName={mentorName ?? summary.mentorName} />
        </div>
      )}
    </div>
  );
}
