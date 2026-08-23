"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ProgramSummary } from "@/components/programs/ProgramSummary";
import { RoadmapReadOnlyView } from "@/components/roadmaps/RoadmapWeekView";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import { getProgram } from "@/lib/api/programs";
import { getRoadmap, publishRoadmap } from "@/lib/api/roadmaps";
import { roadmapScopeLabel } from "@/lib/labels";
import { fullName } from "@/lib/names";
import type { InternshipProgram, Roadmap } from "@/types";

export default function RoadmapDetailPage() {
  const params = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [program, setProgram] = useState<InternshipProgram | null>(null);
  const [internNames, setInternNames] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [publishing, setPublishing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const map = await getRoadmap(params.id);
      setRoadmap(map);
      const [programData, interns] = await Promise.all([
        getProgram(map.programId).catch(() => null),
        listInternProfiles().catch(() => []),
      ]);
      setProgram(programData);
      setInternNames(
        Object.fromEntries(
          interns
            .filter((ip) => ip.programId === map.programId)
            .map((ip) => [ip.id, fullName(ip.user) || ip.id]),
        ),
      );
    } catch (err) {
      setError(getErrorMessage(err, "Could not load roadmap."));
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function publish() {
    if (!roadmap || roadmap.status !== "DRAFT") return;
    setPublishing(true);
    setMessage("");
    try {
      const updated = await publishRoadmap(roadmap.id);
      setRoadmap(updated);
      setMessage("Roadmap published. Tasks for all weeks are now assigned.");
    } catch (err) {
      setMessage(getErrorMessage(err, "Could not publish roadmap."));
    } finally {
      setPublishing(false);
    }
  }

  if (loading) return <LoadingState label="Loading roadmap…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!roadmap) return <p>Roadmap not found.</p>;

  return (
    <div>
      <PageHeader
        title={roadmap.title}
        description={roadmap.summary}
        actions={
          <>
            <Link href={`/mentor/roadmaps/${roadmap.id}/edit`} className="btn-secondary">
              Edit roadmap
            </Link>
            <Link href={`/mentor/roadmaps/${roadmap.id}/preview`} className="btn-secondary">
              Preview
            </Link>
            {roadmap.status === "DRAFT" ? (
              <button
                type="button"
                className="btn-primary"
                onClick={() => void publish()}
                disabled={publishing}
              >
                {publishing ? "Publishing…" : "Publish roadmap"}
              </button>
            ) : null}
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <StatusBadge kind="roadmap" value={roadmap.status} />
        <span className="rounded-full bg-brand-light px-2.5 py-1 text-xs font-semibold text-brand-dark">
          {roadmapScopeLabel[roadmap.scope]}
        </span>
        <span className="text-sm text-ink-muted">{program?.title}</span>
      </div>
      {message ? (
        <p className="mb-4 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700" role="status">
          {message}
        </p>
      ) : null}

      {program ? (
        <section className="card mb-4 p-5">
          <h2 className="section-title mb-3">Program summary</h2>
          <ProgramSummary program={program} compact />
        </section>
      ) : null}

      <RoadmapReadOnlyView roadmap={roadmap} internNames={internNames} />
    </div>
  );
}
