"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { InternChipPicker } from "@/components/interns/InternChips";
import { ProgramSummary } from "@/components/programs/ProgramSummary";
import { RoadmapGenerationLoader } from "@/components/roadmaps/RoadmapGenerationLoader";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import { listPrograms } from "@/lib/api/programs";
import { generateRoadmap } from "@/lib/api/roadmaps";
import { fullName } from "@/lib/names";
import type { InternshipProgram } from "@/types";

export default function GenerateRoadmapPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [myPrograms, setMyPrograms] = useState<InternshipProgram[]>([]);
  const [interns, setInterns] = useState<
    Awaited<ReturnType<typeof listInternProfiles>>
  >([]);
  const [scope, setScope] = useState<"PROGRAM" | "GROUP" | "INDIVIDUAL">("PROGRAM");
  const [programId, setProgramId] = useState("");
  const [selectedInternIds, setSelectedInternIds] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [programs, ips] = await Promise.all([listPrograms(), listInternProfiles()]);
      const mine = programs.filter((p) => p.mentorId === user?.id);
      setMyPrograms(mine);
      setInterns(ips);
      setProgramId((prev) => prev || mine[0]?.id || "");
    } catch (err) {
      setError(getErrorMessage(err, "Could not load programs."));
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedProgram = myPrograms.find((p) => p.id === programId);

  const internOptions = useMemo(
    () =>
      interns
        .filter((ip) => ip.mentorId === user?.id && ip.programId === programId)
        .map((ip) => ({ id: ip.id, name: fullName(ip.user) || ip.id })),
    [interns, programId, user?.id],
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selectedProgram || saving) return;
    if (scope !== "PROGRAM" && selectedInternIds.length === 0) {
      setMessage("Select at least one intern for this roadmap scope.");
      return;
    }
    if (scope === "INDIVIDUAL" && selectedInternIds.length !== 1) {
      setMessage("Individual scope requires exactly one intern.");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const roadmap = await generateRoadmap({
        program_id: Number(selectedProgram.id),
        assignment_scope: scope,
        selected_intern_ids:
          scope === "PROGRAM" ? [] : selectedInternIds.map(Number),
      });
      router.push(`/mentor/roadmaps/${roadmap.id}/edit`);
    } catch (err) {
      setSaving(false);
      setMessage(
        getErrorMessage(
          err,
          "AI roadmap generation is currently unavailable. Please try again.",
        ),
      );
    }
  }

  if (loading) return <LoadingState label="Loading…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  if (saving) {
    return (
      <div>
        <PageHeader
          title="Generate AI roadmap"
          description="Please wait while your draft roadmap is being prepared."
        />
        <RoadmapGenerationLoader />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Generate AI roadmap"
        description="Choose roadmap scope, then request generation. Output is always saved as Draft for mentor review."
        actions={<Link href="/mentor/roadmaps" className="btn-secondary">Cancel</Link>}
      />
      <form onSubmit={onSubmit} className="card mx-auto max-w-2xl space-y-4 p-6">
        <div>
          <label className="label" htmlFor="programId">Program</label>
          <select
            id="programId"
            className="input"
            value={programId}
            onChange={(e) => {
              setProgramId(e.target.value);
              setSelectedInternIds([]);
            }}
            required
          >
            {myPrograms.map((p) => (
              <option key={p.id} value={p.id}>{p.title}</option>
            ))}
          </select>
        </div>
        {selectedProgram ? (
          <div className="rounded-xl border border-line bg-surface-muted/70 p-4">
            <p className="mb-2 text-sm font-semibold text-ink">Program summary</p>
            <ProgramSummary program={selectedProgram} compact />
          </div>
        ) : null}
        <fieldset>
          <legend className="label">Roadmap scope</legend>
          <div className="space-y-2">
            {(
              [
                ["PROGRAM", "Entire Program"],
                ["GROUP", "Selected Interns"],
                ["INDIVIDUAL", "Individual Intern"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="scope"
                  value={value}
                  checked={scope === value}
                  onChange={() => {
                    setScope(value);
                    setSelectedInternIds([]);
                  }}
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>
        {scope !== "PROGRAM" ? (
          <InternChipPicker
            options={internOptions}
            selectedIds={selectedInternIds}
            onChange={(ids) => {
              if (scope === "INDIVIDUAL") {
                setSelectedInternIds(ids.slice(-1));
              } else {
                setSelectedInternIds(ids);
              }
            }}
            label={scope === "INDIVIDUAL" ? "Assigned intern" : "Assigned interns"}
          />
        ) : null}
        {message ? (
          <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {message}
          </p>
        ) : null}
        <button type="submit" className="btn-primary" disabled={!programId}>
          Request AI generation
        </button>
      </form>
    </div>
  );
}
