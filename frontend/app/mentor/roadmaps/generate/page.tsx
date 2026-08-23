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
import {
  buildRoadmapPrompt,
  continueRoadmapGeneration,
  type RoadmapPromptPreview,
} from "@/lib/api/roadmaps";
import { fullName } from "@/lib/names";
import type { InternshipProgram } from "@/types";

type Step = "form" | "building" | "preview" | "generating";

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
  const [selectedProgramSkills, setSelectedProgramSkills] = useState<string[]>([]);
  const [customFocusSkills, setCustomFocusSkills] = useState<string[]>([]);
  const [customSkillDraft, setCustomSkillDraft] = useState("");
  const [message, setMessage] = useState("");
  const [step, setStep] = useState<Step>("form");
  const [preview, setPreview] = useState<RoadmapPromptPreview | null>(null);

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
  const programSkills = selectedProgram?.skillsToDevelop || [];

  const internOptions = useMemo(
    () =>
      interns
        .filter((ip) => ip.mentorId === user?.id && ip.programId === programId)
        .map((ip) => ({ id: ip.id, name: fullName(ip.user) || ip.id })),
    [interns, programId, user?.id],
  );

  const mentorFocusSkills = useMemo(() => {
    const combined = [...selectedProgramSkills, ...customFocusSkills];
    const seen = new Set<string>();
    return combined.filter((skill) => {
      const key = skill.trim().toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [selectedProgramSkills, customFocusSkills]);

  function resetFocusSkills() {
    setSelectedProgramSkills([]);
    setCustomFocusSkills([]);
    setCustomSkillDraft("");
  }

  function addCustomSkill() {
    const value = customSkillDraft.trim();
    if (!value) return;
    const exists = mentorFocusSkills.some(
      (skill) => skill.toLowerCase() === value.toLowerCase(),
    );
    if (!exists) {
      setCustomFocusSkills((prev) => [...prev, value]);
    }
    setCustomSkillDraft("");
  }

  async function onBuildPrompt(e: FormEvent) {
    e.preventDefault();
    if (!selectedProgram || step !== "form") return;
    if (scope !== "PROGRAM" && selectedInternIds.length === 0) {
      setMessage("Select at least one intern for this roadmap scope.");
      return;
    }
    if (scope === "INDIVIDUAL" && selectedInternIds.length !== 1) {
      setMessage("Individual scope requires exactly one intern.");
      return;
    }

    setStep("building");
    setMessage("");
    setPreview(null);
    try {
      const result = await buildRoadmapPrompt({
        program_id: Number(selectedProgram.id),
        assignment_scope: scope,
        selected_intern_ids:
          scope === "PROGRAM" ? [] : selectedInternIds.map(Number),
        mentor_focus_skills: scope === "INDIVIDUAL" ? mentorFocusSkills : [],
      });
      setPreview(result);
      setStep("preview");
    } catch (err) {
      setStep("form");
      setMessage(
        getErrorMessage(
          err,
          "AI roadmap generation is currently unavailable. Please try again.",
        ),
      );
    }
  }

  async function onContinue() {
    if (!preview?.preview_id || step !== "preview") return;
    setStep("generating");
    setMessage("");
    try {
      const roadmap = await continueRoadmapGeneration(preview.preview_id);
      router.push(`/mentor/roadmaps/${roadmap.id}/edit`);
    } catch (err) {
      setStep("preview");
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

  if (step === "building") {
    return (
      <div>
        <PageHeader
          title="Generate AI roadmap"
          description="Please wait while the AI roadmap prompt is prepared."
        />
        <RoadmapGenerationLoader
          title="Preparing your AI roadmap prompt..."
          description="AI is analyzing the program, scope, skills, references, and personalization data."
          statusMessages={[
            "Preparing program context...",
            "Extracting usable reference material...",
            "Building the AI roadmap prompt...",
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
          title="Generate AI roadmap"
          description="Please wait while your draft roadmap is being prepared."
        />
        <RoadmapGenerationLoader
          title="Generating your internship roadmap..."
          description="AI is converting the reviewed prompt and program context into a structured roadmap."
          statusMessages={[
            "Sending the reviewed prompt to the roadmap generator...",
            "Generating weeks and tasks...",
            "Validating roadmap structure...",
            "Saving your draft roadmap...",
          ]}
        />
      </div>
    );
  }

  if (step === "preview" && preview) {
    return (
      <div>
        <PageHeader
          title="Review AI Roadmap Prompt"
          description="This is the complete instruction package that will be sent to AI to generate the roadmap. It includes the program requirements, scope rules, skills, reference material, and personalization information."
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
              <h3 className="text-sm font-semibold text-ink">Final Roadmap Generation Prompt</h3>
              <pre className="mt-2 max-h-[28rem] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-surface-muted/70 p-4 text-xs leading-relaxed text-ink">
                {preview.final_roadmap_generation_prompt}
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
              Continue to Generate Roadmap
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Generate AI roadmap"
        description="Choose roadmap scope, then build the AI prompt. You will review the final prompt before roadmap generation."
        actions={<Link href="/mentor/roadmaps" className="btn-secondary">Cancel</Link>}
      />
      <form onSubmit={onBuildPrompt} className="card mx-auto max-w-2xl space-y-4 p-6">
        <div>
          <label className="label" htmlFor="programId">Program</label>
          <select
            id="programId"
            className="input"
            value={programId}
            onChange={(e) => {
              setProgramId(e.target.value);
              setSelectedInternIds([]);
              resetFocusSkills();
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
                    resetFocusSkills();
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

        {scope === "INDIVIDUAL" ? (
          <section className="space-y-3 rounded-xl border border-dashed border-line p-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">Skills to Focus On</h2>
              <p className="mt-1 text-xs text-ink-muted">
                Optional. Selected skills receive extra emphasis for this Individual roadmap.
                Program Skills to Develop still remain required.
              </p>
            </div>
            <div className="space-y-2">
              {programSkills.length === 0 ? (
                <p className="text-sm text-ink-muted">
                  This program has no Skills to Develop listed.
                </p>
              ) : (
                programSkills.map((skill) => {
                  const checked = selectedProgramSkills.includes(skill);
                  return (
                    <label key={skill} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setSelectedProgramSkills((prev) =>
                            checked
                              ? prev.filter((item) => item !== skill)
                              : [...prev, skill],
                          );
                        }}
                      />
                      {skill}
                    </label>
                  );
                })
              )}
            </div>
            {customFocusSkills.length ? (
              <ul className="flex flex-wrap gap-2">
                {customFocusSkills.map((skill) => (
                  <li
                    key={skill}
                    className="inline-flex items-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-3 py-1.5 text-sm"
                  >
                    {skill}
                    <button
                      type="button"
                      className="text-brand-dark"
                      onClick={() =>
                        setCustomFocusSkills((prev) => prev.filter((item) => item !== skill))
                      }
                      aria-label={`Remove ${skill}`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <input
                className="input flex-1"
                value={customSkillDraft}
                onChange={(e) => setCustomSkillDraft(e.target.value)}
                placeholder="Add custom skill"
              />
              <button type="button" className="btn-secondary" onClick={addCustomSkill}>
                + Add Custom Skill
              </button>
            </div>
          </section>
        ) : null}

        {message ? (
          <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {message}
          </p>
        ) : null}
        <button type="submit" className="btn-primary" disabled={!programId}>
          Build AI Roadmap Prompt
        </button>
      </form>
    </div>
  );
}
