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
import { listAssignments } from "@/lib/api/tasks";
import { formatDate } from "@/lib/labels";
import { fullName } from "@/lib/names";
import type { TaskAssignment } from "@/types";

export default function MentorReviewsPage() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<TaskAssignment[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ips, assigns] = await Promise.all([
        listInternProfiles(),
        listAssignments(),
      ]);
      const myInterns = ips.filter((ip) => ip.mentorId === user?.id);
      const internIds = new Set(myInterns.map((ip) => ip.id));
      const names: Record<string, string> = {};
      myInterns.forEach((ip) => {
        names[ip.id] = fullName(ip.user) || ip.id;
      });
      setQueue(
        assigns
          .filter(
            (ta) =>
              internIds.has(ta.internProfileId) &&
              (ta.status === "SUBMITTED" || ta.status === "NEEDS_REVISION"),
          )
          .map((ta) => ({
            ...ta,
            internName: ta.internName || names[ta.internProfileId] || "—",
          })),
      );
    } catch (err) {
      setError(getErrorMessage(err, "Could not load review queue."));
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState label="Loading reviews…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="Submission reviews"
        description="Review each intern’s submission individually, provide feedback, and assign an integer score from 0–100."
      />
      <DataTable
        rows={queue}
        mobileTitle={(row) => row.taskTitle || row.id}
        columns={[
          {
            key: "task",
            header: "Task Name",
            render: (row) => row.taskTitle || "—",
          },
          {
            key: "program",
            header: "Program",
            render: (row) => row.programTitle || "—",
          },
          {
            key: "week",
            header: "Week",
            render: (row) =>
              row.weekNumber != null && row.weekNumber !== undefined
                ? `Week ${row.weekNumber}`
                : "—",
          },
          {
            key: "intern",
            header: "Intern",
            render: (row) => row.internName || "—",
          },
          {
            key: "status",
            header: "Status",
            render: (row) => <StatusBadge kind="task" value={row.status} />,
          },
          {
            key: "deadline",
            header: "Deadline",
            render: (row) => formatDate(row.deadline),
          },
          {
            key: "action",
            header: "Action",
            render: (row) => (
              <Link href={`/mentor/reviews/${row.id}`} className="btn-primary px-3 py-1.5 text-xs">
                Review
              </Link>
            ),
          },
        ]}
      />
    </div>
  );
}
