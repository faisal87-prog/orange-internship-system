"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { DataTable } from "@/components/ui/DataTable";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useAuth } from "@/context/AuthContext";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import { listPrograms } from "@/lib/api/programs";
import { listFinalSummaries } from "@/lib/api/reports";
import { fullName } from "@/lib/names";
import { formatScoreOutOf100 } from "@/lib/weeklyScore";
import type { FinalSummary } from "@/types";

export default function MentorFinalSummariesPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<FinalSummary[]>([]);
  const [internNames, setInternNames] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [programs, ips, finals] = await Promise.all([
        listPrograms(),
        listInternProfiles(),
        listFinalSummaries(),
      ]);
      const myProgramIds = new Set(
        programs.filter((p) => p.mentorId === user?.id).map((p) => p.id),
      );
      const names: Record<string, string> = {};
      ips.forEach((ip) => {
        names[ip.id] = fullName(ip.user) || ip.id;
      });
      setInternNames(names);
      setSummaries(finals.filter((fs) => myProgramIds.has(fs.programId)));
    } catch (err) {
      setError(getErrorMessage(err, "Could not load final summaries."));
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading summaries…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="Final internship summaries"
        description="Generate, review, approve, and download PDF. Final Score is calculated from approved weekly reports."
        actions={
          <Link href="/mentor/final-summaries/generate" className="btn-primary">
            Generate summary
          </Link>
        }
      />
      <DataTable
        rows={summaries}
        mobileTitle={(row) => row.id}
        columns={[
          {
            key: "intern",
            header: "Intern",
            render: (row) => internNames[row.internProfileId] || "—",
          },
          {
            key: "status",
            header: "Status",
            render: (row) => <StatusBadge kind="ai" value={row.status} />,
          },
          {
            key: "preview",
            header: "Summary preview",
            render: (row) => (
              <p className="max-w-xs text-xs text-ink-muted line-clamp-2">
                {row.content.overallPerformanceSummary}
              </p>
            ),
          },
          {
            key: "score",
            header: "Final score",
            render: (row) =>
              typeof row.mentorFinalScore === "number"
                ? formatScoreOutOf100(row.mentorFinalScore)
                : "No scored weeks available.",
          },
          {
            key: "action",
            header: "Action",
            render: (row) => (
              <Link href={`/mentor/final-summaries/${row.id}`} className="btn-secondary px-3 py-1.5 text-xs">
                Open
              </Link>
            ),
          },
        ]}
      />
    </div>
  );
}
