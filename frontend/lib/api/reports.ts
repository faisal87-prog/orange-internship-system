import { adaptFinalSummary, adaptWeeklyReport } from "@/lib/api/adapters";
import { apiDownload, apiRequest, unwrapList } from "@/lib/api/client";
import type { FinalSummary, WeeklyReport } from "@/types";

export async function listWeeklyReports(): Promise<WeeklyReport[]> {
  const data = await apiRequest("/api/reports/weekly/");
  return unwrapList(data).map(adaptWeeklyReport);
}

export async function getWeeklyReport(id: string): Promise<
  WeeklyReport & {
    overallWeeklyScore?: number | null;
    pdfUrl?: string | null;
    performanceComparison?: import("@/components/reports/WeeklyPerformanceComparisonTable").PerformanceComparison;
  }
> {
  const raw = await apiRequest<any>(`/api/reports/weekly/${id}/`);
  return {
    ...adaptWeeklyReport(raw),
    overallWeeklyScore: raw.overall_weekly_score,
    pdfUrl: raw.pdf_url,
    performanceComparison: raw.performance_comparison,
  };
}

export async function updateWeeklyReport(id: string, payload: Record<string, unknown>) {
  const raw = await apiRequest<any>(`/api/reports/weekly/${id}/`, {
    method: "PATCH",
    body: payload,
  });
  return {
    ...adaptWeeklyReport(raw),
    overallWeeklyScore: raw.overall_weekly_score,
    pdfUrl: raw.pdf_url,
    performanceComparison: raw.performance_comparison,
  };
}

export async function approveWeeklyReport(id: string) {
  const raw = await apiRequest<any>(`/api/reports/weekly/${id}/approve/`, {
    method: "POST",
  });
  return adaptWeeklyReport(raw);
}

export async function downloadWeeklyReportPdf(id: string) {
  await apiDownload(`/api/reports/weekly/${id}/download_pdf/`, `weekly-report-${id}.pdf`);
}

export type WeeklyReportPromptPreview = {
  preview_id: string;
  prompt_title: string;
  final_weekly_report_generation_prompt: string;
  important_constraints: string[];
  personalization_points: string[];
  missing_context_notes?: string[];
  program_id: number;
  intern_id: number;
  roadmap_week_id: number;
  week_number: number;
  overall_weekly_score: number | null;
};

export async function buildWeeklyReportPrompt(payload: {
  program_id: number;
  intern_id: number;
  roadmap_week_id: number;
}) {
  return apiRequest<WeeklyReportPromptPreview>("/api/reports/weekly/generate/prompt/", {
    method: "POST",
    body: payload,
  });
}

export async function continueWeeklyReportGeneration(previewId: string) {
  const raw = await apiRequest<any>("/api/reports/weekly/generate/continue/", {
    method: "POST",
    body: { preview_id: previewId },
  });
  return {
    ...adaptWeeklyReport(raw),
    overallWeeklyScore: raw.overall_weekly_score,
    pdfUrl: raw.pdf_url,
  };
}

export async function listFinalSummaries(): Promise<FinalSummary[]> {
  const data = await apiRequest("/api/reports/final-summaries/");
  return unwrapList(data).map(adaptFinalSummary);
}

export async function getFinalSummary(id: string): Promise<
  FinalSummary & {
    pdfUrl?: string | null;
    weekPerformance?: import("@/components/final-summary/InternshipWeekPerformanceTable").WeekPerformance;
  }
> {
  const raw = await apiRequest<any>(`/api/reports/final-summaries/${id}/`);
  return {
    ...adaptFinalSummary(raw),
    pdfUrl: raw.pdf_url,
    weekPerformance: raw.week_performance,
  };
}

export async function updateFinalSummary(id: string, payload: Record<string, unknown>) {
  const raw = await apiRequest<any>(`/api/reports/final-summaries/${id}/`, {
    method: "PATCH",
    body: payload,
  });
  return adaptFinalSummary(raw);
}

export async function approveFinalSummary(id: string) {
  const raw = await apiRequest<any>(`/api/reports/final-summaries/${id}/approve/`, {
    method: "POST",
  });
  return adaptFinalSummary(raw);
}

export async function downloadFinalSummaryPdf(id: string) {
  await apiDownload(
    `/api/reports/final-summaries/${id}/download_pdf/`,
    `final-internship-summary-${id}.pdf`,
  );
}

export type FinalSummaryPromptPreview = {
  preview_id: string;
  prompt_title: string;
  final_final_summary_generation_prompt: string;
  important_constraints: string[];
  personalization_points: string[];
  missing_context_notes?: string[];
  program_id: number;
  intern_id: number;
};

export async function buildFinalSummaryPrompt(payload: {
  program_id: number;
  intern_id: number;
}) {
  return apiRequest<FinalSummaryPromptPreview>(
    "/api/reports/final-summaries/generate/prompt/",
    {
      method: "POST",
      body: payload,
    },
  );
}

export async function continueFinalSummaryGeneration(previewId: string) {
  const raw = await apiRequest<any>("/api/reports/final-summaries/generate/continue/", {
    method: "POST",
    body: { preview_id: previewId },
  });
  return { ...adaptFinalSummary(raw), pdfUrl: raw.pdf_url };
}
