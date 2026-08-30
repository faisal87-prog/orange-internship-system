"use client";

export type WeekPerformanceRow = {
  week_number: number;
  weekly_score: number | null;
  completed_tasks: number;
  total_tasks: number;
  needs_revision: number;
  main_focus: string | null;
};

export type WeekPerformance = {
  weeks: WeekPerformanceRow[];
};

function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return String(value);
}

export function InternshipWeekPerformanceTable({
  weekPerformance,
}: {
  weekPerformance?: WeekPerformance | null;
}) {
  const weeks = weekPerformance?.weeks || [];

  return (
    <section className="card space-y-3 p-5">
      <h2 className="section-title text-brand-dark">Internship Performance by Week</h2>
      {weeks.length === 0 ? (
        <p className="text-sm text-ink-muted">No roadmap weeks available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="border-b-2 border-brand bg-brand-soft/60 text-left">
                <th className="px-3 py-2 font-semibold text-brand-dark">Week</th>
                <th className="px-3 py-2 font-semibold text-brand-dark">Score</th>
                <th className="px-3 py-2 font-semibold text-brand-dark">Completed Tasks</th>
                <th className="px-3 py-2 font-semibold text-brand-dark">Needs Revision</th>
                <th className="px-3 py-2 font-semibold text-brand-dark">Main Focus</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((week) => (
                <tr key={week.week_number} className="border-b border-line/70">
                  <td className="px-3 py-2 font-medium text-ink whitespace-nowrap">
                    Week {week.week_number}
                  </td>
                  <td className="px-3 py-2 text-ink-muted text-center">
                    {formatScore(week.weekly_score)}
                  </td>
                  <td className="px-3 py-2 text-ink-muted text-center">
                    {week.completed_tasks}/{week.total_tasks}
                  </td>
                  <td className="px-3 py-2 text-ink-muted text-center">
                    {week.needs_revision}
                  </td>
                  <td className="px-3 py-2 text-ink-muted break-words">
                    {week.main_focus || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
