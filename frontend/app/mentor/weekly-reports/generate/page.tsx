"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AiGenerationLoader } from "@/components/roadmaps/RoadmapGenerationLoader";
import { ErrorState, LoadingState } from "@/components/ui/AsyncState";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/context/AuthContext";
import { listInternProfiles } from "@/lib/api/accounts";
import { getErrorMessage } from "@/lib/api/errors";
import { listPrograms } from "@/lib/api/programs";
import {
  buildWeeklyReportPrompt,
  continueWeeklyReportGeneration,
  type WeeklyReportPromptPreview,
} from "@/lib/api/reports";
import { listRoadmaps } from "@/lib/api/roadmaps";
import { formatScoreOutOf100 } from "@/lib/weeklyScore";
import { fullName } from "@/lib/names";
import type { InternshipProgram, Roadmap } from "@/types";

type Step = "form" | "building" | "preview" | "generating";

export default function GenerateWeeklyReportPage() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [programs, setPrograms] = useState<InternshipProgram[]>([]);
  const [roadmaps, setRoadmaps] = useState<Roadmap[]>([]);
  const [interns, setInterns] = useState<
    Awaited<ReturnType<typeof listInternProfiles>>
  >([]);
  const [programId, setProgramId] = useState("");
  const [internId, setInternId] = useState("");
  const [weekId, setWeekId] = useState("");
  const [message, setMessage] = useState("");
  const [step, setStep] = useState<Step>("form");
  const [preview, setPreview] = useState<WeeklyReportPromptPreview | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [programList, roadmapList, internList] = await Promise.all([
        listPrograms(),
        listRoadmaps(),
        listInternProfiles(),
      ]);
      const mine = programList.filter((p) => p.mentorId === user?.id);
      setPrograms(mine);
      setRoadmaps(roadmapList.filter((r) => r.status === "PUBLISHED"));
      setInterns(internList.filter((ip) => ip.mentorId === user?.id));

      const qProgram = searchParams.get("programId") || "";
      const qIntern = searchParams.get("internId") || "";
      const qWeek = searchParams.get("weekId") || "";
      const initialProgram = qProgram || mine[0]?.id || "";
      setProgramId(initialProgram);
      setInternId(qIntern);
      setWeekId(qWeek);
    } catch (err) {
      setError(getErrorMessage(err, "Could not load weekly report options."));
    } finally {
      setLoading(false);
    }
  }, [searchParams, user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const programInterns = useMemo(
    () =>
      interns
        .filter((ip) => ip.programId === programId)
        .map((ip) => ({ id: ip.id, name: fullName(ip.user) || ip.id })),
    [interns, programId],
  );

  const weekOptions = useMemo(() => {
    const published = roadmaps.filter((r) => r.programId === programId);
    const weeks: { id: string; label: string; weekNumber: number }[] = [];
    for (const roadmap of published) {
      for (const week of roadmap.weeks || []) {
        if (!week.id) continue;
        weeks.push({
          id: week.id,
          weekNumber: week.weekNumber,
          label: `Week ${week.weekNumber} · ${week.weeklyFocus || roadmap.title}`,
        });
      }
    }
    return weeks.sort((a, b) => a.weekNumber - b.weekNumber);
  }, [programId, roadmaps]);

  useEffect(() => {
    if (!internId && programInterns[0]) setInternId(programInterns[0].id);
    if (internId && !programInterns.some((item) => item.id === internId)) {
      setInternId(programInterns[0]?.id || "");
    }
  }, [internId, programInterns]);

  useEffect(() => {
    if (!weekId && weekOptions[0]) setWeekId(weekOptions[0].id);
    if (weekId && !weekOptions.some((item) => item.id === weekId)) {
      setWeekId(weekOptions[0]?.id || "");
    }
  }, [weekId, weekOptions]);

  async function onBuildPrompt(e: FormEvent) {
    e.preventDefault();
    if (!programId || !internId || !weekId || step !== "form") return;
    setStep("building");
    setMessage("");
    setPreview(null);
    try {
      const result = await buildWeeklyReportPrompt({
        program_id: Number(programId),
        intern_id: Number(internId),
        roadmap_week_id: Number(weekId),
      });
      setPreview(result);
      setStep("preview");
    } catch (err) {
      setStep("form");
      setMessage(
        getErrorMessage(
          err,
          "AI weekly report generation is currently unavailable. Please try again.",
        ),
      );
    }
  }

  async function onContinue() {
    if (!preview?.preview_id || step !== "preview") return;
    setStep("generating");
    setMessage("");
    try {
      const report = await continueWeeklyReportGeneration(preview.preview_id);
      router.push(`/mentor/weekly-reports/${report.id}`);
    } catch (err) {
      setStep("preview");
      setMessage(
        getErrorMessage(
          err,
          "AI weekly report generation is currently unavailable. Please try again.",
        ),
      );
    }
  }

  if (loading) return <LoadingState label="Loading…" />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  if (step === "building") {
    return (
      <div>
        <PageHeader
          title="Generate weekly report"
          description="Please wait while the weekly report prompt is prepared."
        />
        <AiGenerationLoader
          title="Preparing your weekly report prompt..."
          description="AI is analyzing the week's objectives, tasks, submissions, feedback, and scores."
          statusMessages={[
            "Gathering week objectives and tasks...",
            "Reviewing submissions and mentor feedback...",
            "Building the weekly report prompt...",
            "Assembling the final prompt package...",
          ]}
        />
      </div>
    );
  }

  if (step === "generating") {
    return (
      <div>
        <PageHeader
          title="Generate weekly report"
          description="Please wait while the draft weekly report is generated."
        />
        <AiGenerationLoader
          title="Generating weekly performance report..."
          description="AI is converting the reviewed weekly context into a structured performance report."
          statusMessages={[
            "Sending the reviewed prompt to the report generator...",
            "Drafting performance sections...",
            "Validating structured report output...",
            "Saving your draft weekly report...",
          ]}
        />
      </div>
    );
  }

  if (step === "preview" && preview) {
    return (
      <div>
        <PageHeader
          title="Review Weekly Report Prompt"
          description="This is the complete instruction package that will be sent to AI to generate the weekly performance report."
          actions={
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setStep("form");
                setMessage("");
              }}
            >
              Back
            </button>
          }
        />
        <div className="mx-auto max-w-4xl space-y-4">
          {message ? (
            <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
              {message}
            </p>
          ) : null}
          <section className="card space-y-3 p-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-brand">
                Prompt Title
              </p>
              <h2 className="mt-1 text-lg font-semibold text-ink">{preview.prompt_title}</h2>
            </div>
            <div>
              <p className="text-sm text-ink-muted">
                Week {preview.week_number} · Overall weekly score context:{" "}
                {typeof preview.overall_weekly_score === "number"
                  ? formatScoreOutOf100(preview.overall_weekly_score)
                  : "No scored tasks available for this week."}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink">
                Final Weekly Report Generation Prompt
              </h3>
              <pre className="mt-2 max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-surface-muted/70 p-4 text-xs leading-relaxed text-ink">
                {preview.final_weekly_report_generation_prompt}
              </pre>
            </div>
          </section>
          <section className="card grid gap-4 p-5 md:grid-cols-2">
            <div>
              <h3 className="text-sm font-semibold text-ink">Important Constraints</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-muted">
                {(preview.important_constraints || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
                {(preview.important_constraints || []).length === 0 ? <li>None</li> : null}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-ink">Personalization Points</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-muted">
                {(preview.personalization_points || []).map((item) => (
                  <li key={item}>{item}</li>
                ))}
                {(preview.personalization_points || []).length === 0 ? <li>None</li> : null}
              </ul>
            </div>
          </section>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setStep("form");
                setMessage("");
              }}
            >
              Back
            </button>
            <button type="button" className="btn-primary" onClick={() => void onContinue()}>
              Continue to Generate Weekly Report
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Generate weekly report"
        description="Select Program, Intern, and published Roadmap Week. You will review the AI prompt before generation."
        actions={<Link href="/mentor/weekly-reports" className="btn-secondary">Cancel</Link>}
      />
      <form onSubmit={onBuildPrompt} className="card mx-auto max-w-xl space-y-4 p-6">
        <div>
          <label className="label" htmlFor="program">Program</label>
          <select
            id="program"
            className="input"
            value={programId}
            onChange={(e) => {
              setProgramId(e.target.value);
              setInternId("");
              setWeekId("");
            }}
            required
          >
            {programs.map((program) => (
              <option key={program.id} value={program.id}>
                {program.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="intern">Intern</label>
          <select
            id="intern"
            className="input"
            value={internId}
            onChange={(e) => setInternId(e.target.value)}
            required
          >
            {programInterns.map((ip) => (
              <option key={ip.id} value={ip.id}>
                {ip.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="week">Week</label>
          <select
            id="week"
            className="input"
            value={weekId}
            onChange={(e) => setWeekId(e.target.value)}
            required
          >
            {weekOptions.map((week) => (
              <option key={week.id} value={week.id}>
                {week.label}
              </option>
            ))}
          </select>
          {weekOptions.length === 0 ? (
            <p className="mt-2 text-xs text-ink-muted">
              No published roadmap weeks are available for this program.
            </p>
          ) : null}
        </div>
        {message ? (
          <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {message}
          </p>
        ) : null}
        <button
          type="submit"
          className="btn-primary"
          disabled={!programId || !internId || !weekId}
        >
          Build Weekly Report Prompt
        </button>
      </form>
    </div>
  );
}
