"use client";

export type PerformanceComparisonWeek = {
  week_number: number;
  weekly_score: number | null;
  completed_tasks: number;
  total_tasks: number;
  needs_revision: number;
  on_time_tasks: number;
};

export type PerformanceComparison = {
  current_week_number: number | null;
  has_previous_weeks: boolean;
  weeks: PerformanceComparisonWeek[];
  change: {
    weekly_score: number | null;
    completed_tasks: number | null;
    needs_revision: number | null;
    on_time_tasks: number | null;
  } | null;
  message?: string | null;
};

function formatChange(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  if (value > 0) return `+${value}`;
  return String(value);
}

function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return String(value);
}

export function WeeklyPerformanceComparisonTable({
  comparison,
}: {
  comparison?: PerformanceComparison | null;
}) {
  if (!comparison) return null;

  if (!comparison.has_previous_weeks) {
    return (
      <section className="card space-y-2 p-5">
        <h2 className="section-title">Weekly Performance Comparison</h2>
        <p className="text-sm text-ink-muted">
          {comparison.message || "No previous week available for comparison."}
        </p>
      </section>
    );
  }

  const weeks = comparison.weeks || [];
  const change = comparison.change || {
    weekly_score: null,
    completed_tasks: null,
    needs_revision: null,
    on_time_tasks: null,
  };

  const rows = [
    {
      metric: "Weekly Score",
      values: weeks.map((week) => formatScore(week.weekly_score)),
      change: formatChange(change.weekly_score),
    },
    {
      metric: "Completed Tasks",
      values: weeks.map((week) => `${week.completed_tasks}/${week.total_tasks}`),
      change: formatChange(change.completed_tasks),
    },
    {
      metric: "Needs Revision",
      values: weeks.map((week) => String(week.needs_revision)),
      change: formatChange(change.needs_revision),
    },
    {
      metric: "On-Time Tasks",
      values: weeks.map((week) => String(week.on_time_tasks)),
      change: formatChange(change.on_time_tasks),
    },
  ];

  return (
    <section className="card space-y-3 p-5">
      <h2 className="section-title">Weekly Performance Comparison</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-line text-left text-ink-muted">
              <th className="px-3 py-2 font-semibold">Metric</th>
              {weeks.map((week) => (
                <th key={week.week_number} className="px-3 py-2 font-semibold whitespace-nowrap">
                  Week {week.week_number}
                </th>
              ))}
              <th className="px-3 py-2 font-semibold">Change</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.metric} className="border-b border-line/70">
                <td className="px-3 py-2 font-medium text-ink whitespace-nowrap">{row.metric}</td>
                {row.values.map((value, index) => (
                  <td key={`${row.metric}-${index}`} className="px-3 py-2 text-ink-muted text-center">
                    {value}
                  </td>
                ))}
                <td className="px-3 py-2 text-ink-muted text-center whitespace-nowrap">{row.change}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
