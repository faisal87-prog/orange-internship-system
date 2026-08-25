export interface WeeklyTaskScore {
  taskTitle: string;
  score: number;
}

export function averageWeeklyScore(scores: WeeklyTaskScore[]): number | null {
  if (!scores.length) return null;
  const total = scores.reduce((sum, row) => sum + row.score, 0);
  return Math.round(total / scores.length);
}

export function formatScoreOutOf100(score: number) {
  const rounded = Math.round(score * 10) / 10;
  const display = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `${display} / 100`;
}

export function formatFinalScoreLabel(
  score: number | null | undefined,
  scoredCount?: number,
) {
  if (typeof score !== "number") {
    return {
      scoreText: "No scored weeks available.",
      detail: undefined as string | undefined,
    };
  }
  return {
    scoreText: formatScoreOutOf100(score),
    detail:
      typeof scoredCount === "number"
        ? `Calculated from ${scoredCount} scored weekly report${scoredCount === 1 ? "" : "s"}`
        : undefined,
  };
}
