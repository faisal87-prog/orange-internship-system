import type {
  FinalSummary,
  InternshipProgram,
  InternProfile,
  LearningResource,
  ReferenceMaterial,
  ResourceKind,
  Roadmap,
  RoadmapScope,
  RoadmapWeek,
  SkillLevel,
  Submission,
  Task,
  TaskAssignment,
  TaskRequirementType,
  TaskSource,
  TaskStatus,
  User,
  UserRole,
  WeeklyReport,
} from "@/types";

export function splitNameSafe(fullName: string) {
  const parts = (fullName || "").trim().split(/\s+/).filter(Boolean);
  return {
    firstName: parts[0] || fullName || "",
    lastName: parts.slice(1).join(" "),
  };
}

function splitName(fullName: string) {
  return splitNameSafe(fullName);
}

export function fullNameFromUser(user: Pick<User, "firstName" | "lastName">) {
  return [user.firstName, user.lastName].filter(Boolean).join(" ").trim();
}

function mapResourceKind(value: string | undefined): ResourceKind {
  const upper = (value || "").toUpperCase();
  if (upper === "DOCX") return "DOC";
  if (upper === "PPTX") return "PPT";
  if (["PDF", "DOC", "PPT", "IMAGE", "ZIP", "LINK", "OTHER"].includes(upper)) {
    return upper as ResourceKind;
  }
  return "OTHER";
}

function difficultyLabel(value: string | undefined) {
  switch ((value || "").toUpperCase()) {
    case "EASY":
      return "Beginner";
    case "MEDIUM":
      return "Intermediate";
    case "HARD":
      return "Advanced";
    default:
      return value || "";
  }
}

function difficultyToApi(value: string | undefined) {
  const lower = (value || "").toLowerCase();
  if (lower.includes("hard") || lower.includes("advanced")) return "HARD";
  if (lower.includes("medium") || lower.includes("intermediate")) return "MEDIUM";
  if (["EASY", "MEDIUM", "HARD"].includes((value || "").toUpperCase())) {
    return (value || "").toUpperCase();
  }
  return "EASY";
}

function minutesToLabel(minutes: number | undefined) {
  if (!minutes && minutes !== 0) return "";
  if (minutes % 60 === 0) return `${minutes / 60} hours`;
  if (minutes < 60) return `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return `${hours}h ${rest}m`;
}

function parseEstimatedMinutes(value: string | number | undefined) {
  if (typeof value === "number") return value;
  if (!value) return 60;
  const match = String(value).match(/(\d+(\.\d+)?)/);
  if (!match) return 60;
  const amount = Number(match[1]);
  if (String(value).toLowerCase().includes("minute")) return Math.round(amount);
  return Math.round(amount * 60);
}

export function adaptUser(raw: any): User {
  const name = splitName(raw.full_name || `${raw.first_name || ""} ${raw.last_name || ""}`);
  const mentorProfile = raw.mentor_profile;
  return {
    id: String(raw.id),
    email: raw.email || "",
    username: raw.username || "",
    firstName: name.firstName,
    lastName: name.lastName,
    role: raw.role as UserRole,
    isActive: Boolean(raw.is_active ?? raw.isActive ?? true),
    phoneNumber: raw.phone_number || raw.phoneNumber || "",
    department: mentorProfile?.department || raw.department,
    jobTitle: mentorProfile?.job_title || raw.jobTitle,
  };
}

export function adaptMe(raw: any): User {
  return adaptUser(raw);
}

export function adaptInternProfile(raw: any): InternProfile {
  return {
    id: String(raw.id),
    userId: String(raw.user?.id ?? raw.user),
    mentorId: String(raw.mentor?.id ?? raw.mentor),
    programId: raw.program ? String(raw.program?.id ?? raw.program) : "",
    preferences: "",
    learningGoals: raw.learning_goals || raw.learningGoals || "",
    skills: (raw.skills || []).map((skill: any) => ({
      name: skill.skill_name || skill.name,
      level: Number(skill.skill_level || skill.level) as SkillLevel,
    })),
    major: raw.major || "",
    university: raw.university || "",
  };
}

export function adaptResource(raw: any): LearningResource {
  const fileUrl = resolveMediaUrl(raw.file_url || "");
  const externalUrl = String(raw.external_url || raw.externalUrl || raw.externalLink || "").trim();
  let fileName = raw.original_file_name || raw.file_name || raw.fileName;
  if (!fileName && typeof raw.file === "string" && raw.file) {
    fileName = raw.file.split("/").pop();
  }
  const href = fileUrl || externalUrl || raw.href || "#";
  return {
    id: String(raw.id),
    title: raw.title,
    kind: mapResourceKind(raw.resource_type || raw.kind),
    fileName: fileName || undefined,
    href,
    externalUrl: externalUrl || undefined,
  };
}

export function adaptReferenceMaterial(raw: any): ReferenceMaterial {
  return {
    ...adaptResource(raw),
    programId: String(raw.program?.id ?? raw.program),
  };
}

export function adaptProgram(raw: any): InternshipProgram {
  return {
    id: String(raw.id),
    mentorId: String(raw.mentor?.id ?? raw.mentor),
    title: raw.title,
    description: raw.description || "",
    role: raw.role || "",
    startDate: raw.start_date || raw.startDate,
    endDate: raw.end_date || raw.endDate,
    durationWeeks: Number(raw.duration_weeks ?? raw.durationWeeks ?? 0),
    skillsToDevelop: raw.skills_to_develop || raw.skillsToDevelop || [],
    goals: raw.goals || "",
    skillsNeeded: raw.skills_needed || raw.skillsNeeded || [],
    expectedOutcome: raw.expected_outcome || raw.expectedOutcome || "",
    finalProject: raw.final_project || raw.finalProject || "",
    status: raw.status,
    maxInterns: Number(raw.maximum_interns ?? raw.max_interns ?? raw.maxInterns ?? 0),
    department: raw.department || "",
    weeklyHours: Number(raw.weekly_hours ?? raw.weeklyHours ?? 0),
    additionalInstructions:
      raw.additional_instructions || raw.additionalInstructions || "",
  };
}

export function adaptRoadmapWeek(raw: any): RoadmapWeek {
  return {
    id: raw.id != null ? String(raw.id) : undefined,
    weekNumber: Number(raw.week_number ?? raw.weekNumber),
    weeklyFocus: raw.weekly_focus || raw.weeklyFocus || "",
    weeklyLearningObjectives: raw.learning_objectives || raw.weeklyLearningObjectives || [],
    suggestedTasks: (raw.tasks || raw.suggestedTasks || []).map((task: any) => ({
      id: String(task.id),
      title: task.title,
      description: task.description || "",
      difficulty: difficultyLabel(task.difficulty),
      estimatedTime: minutesToLabel(task.estimated_time_minutes),
      deliverable: task.deliverable || "",
      successCriteria: task.success_criteria || task.successCriteria || "",
      source: (task.source || "MANUAL") as TaskSource,
      requirementType: (task.requirement_type || task.requirementType || "REQUIRED") as TaskRequirementType,
      dueDate: task.due_date || task.dueDate,
      assignedInternIds: (task.assigned_intern_ids || []).map(String),
    })),
    expectedSkillsGained: raw.expected_skills_gained || raw.expectedSkillsGained || [],
    mentorNotes: raw.mentor_notes || raw.mentorNotes || "",
  };
}

export function adaptRoadmap(raw: any): Roadmap {
  return {
    id: String(raw.id),
    programId: String(raw.program?.id ?? raw.program),
    title: raw.title,
    summary: raw.summary || "",
    scope: (raw.assignment_scope || raw.scope || "PROGRAM") as RoadmapScope,
    status: raw.status,
    numberOfWeeks: Number(raw.number_of_weeks ?? raw.numberOfWeeks ?? 0),
    weeks: (raw.weeks || []).map(adaptRoadmapWeek),
    assignedInternIds: (raw.assigned_intern_ids || raw.assigned_interns || []).map((item: any) =>
      String(typeof item === "object" ? item.id : item),
    ),
    publishedAt: raw.published_at || raw.publishedAt,
  };
}

export function adaptTask(raw: any): Task {
  return {
    id: String(raw.id),
    programId: String(raw.program?.id ?? raw.program),
    roadmapId: raw.roadmap_week
      ? String(raw.roadmap_week?.roadmap ?? raw.roadmap_id ?? "")
      : undefined,
    weekNumber: Number(raw.week_number ?? raw.roadmap_week?.week_number ?? 0),
    title: raw.title,
    description: raw.description || "",
    difficulty: difficultyLabel(raw.difficulty),
    estimatedTime: minutesToLabel(raw.estimated_time_minutes),
    deliverable: raw.deliverable || "",
    successCriteria: raw.success_criteria || raw.successCriteria || "",
    source: (raw.source || "MANUAL") as TaskSource,
    requirementType: (raw.requirement_type || "REQUIRED") as TaskRequirementType,
    defaultDeadline: raw.due_date || raw.defaultDeadline,
    resources: (raw.resources || []).map(adaptResource),
  };
}

export function adaptAssignment(raw: any): TaskAssignment {
  return {
    id: String(raw.id),
    taskId: String(raw.task?.id ?? raw.task ?? raw.task_id),
    internProfileId: String(raw.intern?.id ?? raw.intern ?? raw.intern_id),
    status: raw.status as TaskStatus,
    deadline: raw.effective_due_date || raw.due_date_override || raw.task?.due_date || raw.deadline,
    score: raw.score ?? undefined,
    mentorFeedback: raw.mentor_feedback || raw.mentorFeedback || "",
    completedAt: raw.completed_at || raw.completedAt,
  };
}

export function adaptWeeklyReport(raw: any): WeeklyReport {
  return {
    id: String(raw.id),
    internProfileId: String(raw.intern?.id ?? raw.intern),
    programId: String(raw.program?.id ?? raw.program),
    weekNumber: Number(raw.week_number ?? raw.roadmap_week?.week_number ?? 0),
    status: raw.status,
    content: {
      performanceSummary: raw.performance_summary || "",
      achievements: raw.achievements || [],
      learningProgress: raw.learning_progress || "",
      productivityAnalysis: raw.productivity_analysis || "",
      mentorFocusSuggestions: raw.mentor_focus_suggestions || [],
      recommendedFocusNextWeek: raw.recommended_next_focus || "",
    },
    additionalMentorNotes: raw.additional_mentor_notes || "",
    approvedAt: raw.approved_at,
  };
}

export function adaptFinalSummary(raw: any): FinalSummary {
  return {
    id: String(raw.id),
    internProfileId: String(raw.intern?.id ?? raw.intern),
    programId: String(raw.program?.id ?? raw.program),
    status: raw.status,
    content: {
      overallPerformanceSummary: raw.overall_performance_summary || "",
      learningJourney: raw.learning_journey || "",
      mainAchievements: raw.main_achievements || [],
      goalAchievement: raw.goal_achievement || "",
      finalPerformanceSummary: raw.final_performance_summary || "",
    },
    mentorFinalScore: raw.final_score ?? undefined,
    mentorFinalComments: raw.mentor_comments || "",
    additionalMentorNotes: raw.additional_mentor_notes || "",
    pdfAvailable: Boolean(raw.pdf_available || raw.pdf_url || raw.pdf_file),
    approvedAt: raw.approved_at,
  };
}

export function programToApiPayload(input: Partial<InternshipProgram> & Record<string, unknown>) {
  return {
    title: input.title,
    description: input.description,
    role: input.role,
    start_date: input.startDate || input.start_date,
    end_date: input.endDate || input.end_date,
    duration_weeks: Number(input.durationWeeks ?? input.duration_weeks),
    department: input.department,
    weekly_hours: Number(input.weeklyHours ?? input.weekly_hours),
    maximum_interns: Number(input.maxInterns ?? input.maximum_interns),
    skills_needed: input.skillsNeeded ?? input.skills_needed ?? [],
    skills_to_develop: input.skillsToDevelop ?? input.skills_to_develop ?? [],
    goals: input.goals ?? "",
    expected_outcome: input.expectedOutcome ?? input.expected_outcome ?? "",
    final_project: input.finalProject ?? input.final_project ?? "",
    additional_instructions:
      input.additionalInstructions ?? input.additional_instructions ?? "",
    status: input.status,
    assigned_intern_ids: (input.assignedInternIds as string[] | undefined)?.map(Number),
  };
}

export function resolveMediaUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  const base = (process.env.NEXT_PUBLIC_API_BASE_URL || "").replace(/\/$/, "");
  return `${base}${url.startsWith("/") ? "" : "/"}${url}`;
}

export function adaptSubmission(raw: any): Submission {
  return {
    id: String(raw.id),
    taskAssignmentId: String(raw.task_assignment?.id ?? raw.task_assignment),
    writtenResponse: raw.written_response || raw.writtenResponse || "",
    files: (raw.files || []).map((file: any) => ({
      id: String(file.id ?? file.original_file_name ?? ""),
      name: file.original_file_name || file.file_name || file.name || "Download",
      url: resolveMediaUrl(file.file_url || file.url || file.file || ""),
    })),
    externalLink: raw.external_url || raw.externalLink || "",
    submissionVersion: Number(raw.version_number ?? raw.submissionVersion ?? 1),
    internNotes: raw.intern_notes || raw.internNotes || "",
    submittedAt: raw.submitted_at || raw.submittedAt,
  };
}

export function taskToApiPayload(input: Record<string, unknown>) {
  const roadmapWeek =
    input.roadmapWeekId != null && input.roadmapWeekId !== ""
      ? Number(input.roadmapWeekId)
      : input.roadmap_week != null && input.roadmap_week !== ""
        ? Number(input.roadmap_week)
        : null;
  const payload: Record<string, unknown> = {
    program: Number(input.programId || input.program),
    roadmap_week: Number.isFinite(roadmapWeek as number) ? roadmapWeek : null,
    title: input.title,
    description: input.description,
    difficulty: difficultyToApi(String(input.difficulty || "EASY")),
    estimated_time_minutes: parseEstimatedMinutes(
      (input.estimatedTime as string) || (input.estimated_time_minutes as number),
    ),
    deliverable: input.deliverable || "",
    success_criteria: input.successCriteria || input.success_criteria || "",
    due_date: input.dueDate || input.due_date || input.deadline,
    requirement_type: input.requirementType || input.requirement_type || "REQUIRED",
    source: input.source || "MANUAL",
  };
  if (input.display_order != null || input.displayOrder != null) {
    payload.display_order = Number(input.display_order ?? input.displayOrder);
  }
  if (input.assignInternIds != null || input.assign_intern_ids != null) {
    payload.assign_intern_ids = (
      (input.assignInternIds as string[]) ||
      (input.assign_intern_ids as string[]) ||
      []
    ).map(Number);
  }
  return payload;
}

export type { };
