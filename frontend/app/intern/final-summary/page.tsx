"use client";

import { useCallback, useEffect, useState } from "react";
import { FinalSummaryContent } from "@/components/final-summary/FinalSummaryContent";
import { InternshipWeekPerformanceTable } from "@/components/final-summary/InternshipWeekPerformanceTable";
import type { WeekPerformance } from "@/components/final-summary/InternshipWeekPerformanceTable";
import { DownloadPdfButton } from "@/components/resources/DownloadPdfButton";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { getErrorMessage } from "@/lib/api/errors";
import { downloadFinalSummaryPdf, getFinalSummary } from "@/lib/api/reports";
import { getInternContext, type InternContext } from "@/lib/intern";
import { formatScoreOutOf100 } from "@/lib/weeklyScore";

export default function InternFinalSummaryPage() {
  const { user } = useAuth();
  const [ctx, setCtx] = useState<InternContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [weekPerformance, setWeekPerformance] = useState<WeekPerformance | null>(null);

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
        setWeekPerformance(
          detail.weekPerformance ?? nextCtx.finalSummary.weekPerformance ?? null,
        );
      } else {
        setWeekPerformance(null);
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
      {!summary ? (
        <EmptyState
          title="No approved final summary"
          description="When your mentor approves your final internship summary, you can view and download it here."
        />
      ) : (
        <div className="space-y-4">
          <InternshipWeekPerformanceTable
            weekPerformance={weekPerformance ?? summary.weekPerformance}
          />
          <section className="card space-y-4 p-6">
            <FinalSummaryContent content={summary.content} />
            <div className="text-sm">
              <h2 className="font-semibold text-ink">Final Score</h2>
              <p className="mt-1 text-ink-muted">
                {typeof summary.mentorFinalScore === "number"
                  ? formatScoreOutOf100(summary.mentorFinalScore)
                  : "No scored weeks available."}
              </p>
            </div>
            {summary.mentorFinalComments ? (
              <div className="text-sm">
                <h2 className="font-semibold text-ink">Mentor comments</h2>
                <p className="mt-1 text-ink-muted">{summary.mentorFinalComments}</p>
              </div>
            ) : null}
            {summary.additionalMentorNotes ? (
              <div className="text-sm">
                <h2 className="font-semibold text-ink">Additional Mentor Notes</h2>
                <p className="mt-1 text-ink-muted">{summary.additionalMentorNotes}</p>
              </div>
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
