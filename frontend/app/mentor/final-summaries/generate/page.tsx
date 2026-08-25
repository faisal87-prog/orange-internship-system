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
  buildFinalSummaryPrompt,
  continueFinalSummaryGeneration,
  type FinalSummaryPromptPreview,
} from "@/lib/api/reports";
import { fullName } from "@/lib/names";
import type { InternshipProgram } from "@/types";

type Step = "form" | "building" | "preview" | "generating";

export default function GenerateFinalSummaryPage() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [programs, setPrograms] = useState<InternshipProgram[]>([]);
  const [interns, setInterns] = useState<
    Awaited<ReturnType<typeof listInternProfiles>>
  >([]);
  const [programId, setProgramId] = useState("");
  const [internId, setInternId] = useState("");
  const [message, setMessage] = useState("");
  const [step, setStep] = useState<Step>("form");
  const [preview, setPreview] = useState<FinalSummaryPromptPreview | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [programList, internList] = await Promise.all([
        listPrograms(),
        listInternProfiles(),
      ]);
      const mine = programList.filter((p) => p.mentorId === user?.id);
      setPrograms(mine);
      setInterns(internList.filter((ip) => ip.mentorId === user?.id));

      const qProgram = searchParams.get("programId") || "";
      const qIntern = searchParams.get("internId") || "";
      const initialProgram = qProgram || mine[0]?.id || "";
      setProgramId(initialProgram);
      setInternId(qIntern);
    } catch (err) {
      setError(getErrorMessage(err, "Could not load final summary options."));
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

  useEffect(() => {
    if (!internId && programInterns[0]) setInternId(programInterns[0].id);
    if (internId && !programInterns.some((item) => item.id === internId)) {
      setInternId(programInterns[0]?.id || "");
    }
  }, [internId, programInterns]);

  async function onBuildPrompt(e: FormEvent) {
    e.preventDefault();
    if (!programId || !internId || step !== "form") return;
    setStep("building");
    setMessage("");
    setPreview(null);
    try {
      const result = await buildFinalSummaryPrompt({
        program_id: Number(programId),
        intern_id: Number(internId),
      });
      setPreview(result);
      setStep("preview");
    } catch (err) {
      setStep("form");
      setMessage(
        getErrorMessage(
          err,
          "AI final summary generation is currently unavailable. Please try again.",
        ),
      );
    }
  }

  async function onContinue() {
    if (!preview?.preview_id || step !== "preview") return;
    setStep("generating");
    setMessage("");
    try {
      const summary = await continueFinalSummaryGeneration(preview.preview_id);
      router.push(`/mentor/final-summaries/${summary.id}`);
    } catch (err) {
      setStep("preview");
      setMessage(
        getErrorMessage(
          err,
          "AI final summary generation is currently unavailable. Please try again.",
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
          title="Generate final summary"
          description="Please wait while the final summary prompt is prepared."
        />
        <AiGenerationLoader
          title="Preparing final summary prompt..."
          description="AI is analyzing the intern's roadmap, tasks, submissions, feedback, weekly reports, and learning progress."
          statusMessages={[
            "Gathering program goals and roadmap weeks...",
            "Reviewing tasks, submissions, and mentor feedback...",
            "Including approved weekly reports...",
            "Assembling the final summary prompt package...",
          ]}
        />
      </div>
    );
  }

  if (step === "generating") {
    return (
      <div>
        <PageHeader
          title="Generate final summary"
          description="Please wait while the draft final summary is generated."
        />
        <AiGenerationLoader
          title="Generating final internship summary..."
          description="AI is synthesizing the intern's full internship performance and learning journey."
          statusMessages={[
            "Sending the reviewed prompt to the summary generator...",
            "Drafting the five summary sections...",
            "Validating structured summary output...",
            "Saving your draft final summary...",
          ]}
        />
      </div>
    );
  }

  if (step === "preview" && preview) {
    return (
      <div>
        <PageHeader
          title="Review Final Summary Prompt"
          description="This is the complete instruction package that will be sent to AI to generate the final internship summary."
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
              <h3 className="text-sm font-semibold text-ink">
                Final Final-Summary Generation Prompt
              </h3>
              <pre className="mt-2 max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-surface-muted/70 p-4 text-xs leading-relaxed text-ink">
                {preview.final_final_summary_generation_prompt}
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
              Continue to Generate Final Summary
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Generate final summary"
        description="Select Program and Intern. You will review the AI prompt before generation. Output is stored as Draft until mentor approval."
        actions={<Link href="/mentor/final-summaries" className="btn-secondary">Cancel</Link>}
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
          {programInterns.length === 0 ? (
            <p className="mt-2 text-xs text-ink-muted">
              No interns are assigned to this program.
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
          disabled={!programId || !internId}
        >
          Build Final Summary Prompt
        </button>
      </form>
    </div>
  );
}
