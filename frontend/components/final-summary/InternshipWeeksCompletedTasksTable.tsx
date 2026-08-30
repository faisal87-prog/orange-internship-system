"use client";

export type WeeksCompletedTasksRow = {
  week_number: number;
  main_focus: string | null;
  completed_task_titles: string[];
};

export type WeeksCompletedTasks = {
  weeks: WeeksCompletedTasksRow[];
};

export function InternshipWeeksCompletedTasksTable({
  weeksCompletedTasks,
}: {
  weeksCompletedTasks?: WeeksCompletedTasks | null;
}) {
  const weeks = weeksCompletedTasks?.weeks || [];

  return (
    <section className="card space-y-3 p-5">
      <h2 className="section-title text-brand-dark">
        Internship Weeks &amp; Completed Tasks
      </h2>
      {weeks.length === 0 ? (
        <p className="text-sm text-ink-muted">No roadmap weeks available.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="border-b-2 border-brand bg-brand-soft/60 text-left">
                <th className="px-3 py-2 font-semibold text-brand-dark whitespace-nowrap">
                  Week
                </th>
                <th className="px-3 py-2 font-semibold text-brand-dark">Main Focus</th>
                <th className="px-3 py-2 font-semibold text-brand-dark">
                  Completed Tasks
                </th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((week) => (
                <tr key={week.week_number} className="border-b border-line/70 align-top">
                  <td className="px-3 py-2 font-medium text-ink whitespace-nowrap">
                    Week {week.week_number}
                  </td>
                  <td className="px-3 py-2 text-ink-muted break-words">
                    {week.main_focus || "—"}
                  </td>
                  <td className="px-3 py-2 text-ink-muted">
                    {week.completed_task_titles.length === 0 ? (
                      <span>No completed tasks recorded.</span>
                    ) : (
                      <ul className="list-disc space-y-0.5 pl-4">
                        {week.completed_task_titles.map((title) => (
                          <li key={title} className="break-words">
                            {title}
                          </li>
                        ))}
                      </ul>
                    )}
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
