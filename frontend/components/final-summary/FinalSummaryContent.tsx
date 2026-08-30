import type { FinalSummary } from "@/types";

type Content = FinalSummary["content"];
type SectionGroup = "all" | "intro" | "narrative";

export function FinalSummaryContent({
  content,
  editable = false,
  onChange,
  sections = "all",
}: {
  content: Content;
  editable?: boolean;
  onChange?: (next: Content) => void;
  /** Which AI sections to render (tables sit between intro and narrative). */
  sections?: SectionGroup;
}) {
  function update<K extends keyof Content>(key: K, value: Content[K]) {
    onChange?.({ ...content, [key]: value });
  }

  const showIntro = sections === "all" || sections === "intro";
  const showNarrative = sections === "all" || sections === "narrative";

  if (!editable) {
    return (
      <div className="space-y-4 text-sm">
        {showIntro ? (
          <>
            <div>
              <h2 className="section-title text-brand-dark">Internship Introduction</h2>
              <p className="mt-1 text-ink-muted">{content.internshipIntroduction}</p>
            </div>
            <div>
              <h2 className="section-title text-brand-dark">Training Summary</h2>
              <p className="mt-1 text-ink-muted">{content.trainingSummary}</p>
            </div>
          </>
        ) : null}
        {showNarrative ? (
          <>
            <div>
              <h2 className="section-title text-brand-dark">Overall Performance Summary</h2>
              <p className="mt-1 text-ink-muted">{content.overallPerformanceSummary}</p>
            </div>
            <div>
              <h2 className="section-title text-brand-dark">Learning Journey</h2>
              <p className="mt-1 text-ink-muted">{content.learningJourney}</p>
            </div>
            <div>
              <h2 className="section-title text-brand-dark">Main Achievements</h2>
              <ul className="mt-1 list-disc pl-5 text-ink-muted">
                {content.mainAchievements.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="section-title text-brand-dark">Goal Achievement</h2>
              <p className="mt-1 text-ink-muted">{content.goalAchievement}</p>
            </div>
            <div>
              <h2 className="section-title text-brand-dark">Final Performance Summary</h2>
              <p className="mt-1 text-ink-muted">{content.finalPerformanceSummary}</p>
            </div>
          </>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-4 text-sm">
      {showIntro ? (
        <>
          <div>
            <label className="label" htmlFor="intro">Internship Introduction</label>
            <textarea
              id="intro"
              className="input"
              rows={3}
              value={content.internshipIntroduction}
              onChange={(e) => update("internshipIntroduction", e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="training">Training Summary</label>
            <textarea
              id="training"
              className="input"
              rows={3}
              value={content.trainingSummary}
              onChange={(e) => update("trainingSummary", e.target.value)}
            />
          </div>
        </>
      ) : null}
      {showNarrative ? (
        <>
          <div>
            <label className="label" htmlFor="overall">Overall Performance Summary</label>
            <textarea
              id="overall"
              className="input"
              rows={3}
              value={content.overallPerformanceSummary}
              onChange={(e) => update("overallPerformanceSummary", e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="journey">Learning Journey</label>
            <textarea
              id="journey"
              className="input"
              rows={3}
              value={content.learningJourney}
              onChange={(e) => update("learningJourney", e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="achievements">
              Main Achievements (one per line)
            </label>
            <textarea
              id="achievements"
              className="input"
              rows={3}
              value={content.mainAchievements.join("\n")}
              onChange={(e) =>
                update(
                  "mainAchievements",
                  e.target.value
                    .split("\n")
                    .map((line) => line.trim())
                    .filter(Boolean),
                )
              }
            />
          </div>
          <div>
            <label className="label" htmlFor="goals">Goal Achievement</label>
            <textarea
              id="goals"
              className="input"
              rows={3}
              value={content.goalAchievement}
              onChange={(e) => update("goalAchievement", e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="final">Final Performance Summary</label>
            <textarea
              id="final"
              className="input"
              rows={3}
              value={content.finalPerformanceSummary}
              onChange={(e) => update("finalPerformanceSummary", e.target.value)}
            />
          </div>
        </>
      ) : null}
    </div>
  );
}
