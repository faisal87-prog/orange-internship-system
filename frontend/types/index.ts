export type UserRole = "ADMIN" | "MENTOR" | "INTERN";

export type ProgramStatus =
  | "DRAFT"
  | "ACTIVE"
  | "COMPLETED"
  | "ARCHIVED"
  | "CANCELLED";

export type RoadmapStatus = "DRAFT" | "PUBLISHED" | "ARCHIVED";
export type RoadmapScope = "PROGRAM" | "GROUP" | "INDIVIDUAL";

export type TaskStatus =
  | "TO_DO"
  | "IN_PROGRESS"
  | "SUBMITTED"
  | "NEEDS_REVISION"
  | "COMPLETED";

export type AiContentStatus = "DRAFT" | "APPROVED" | "REJECTED";
export type TaskSource = "AI_GENERATED" | "MANUAL";
export type TaskRequirementType = "REQUIRED" | "OPTIONAL";
export type SkillLevel = 1 | 2 | 3 | 4 | 5;

export interface User {
  id: string;
  email: string;
  username: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  isActive: boolean;
  phoneNumber?: string;
  department?: string;
  jobTitle?: string;
}

export interface InternProfile {
  id: string;
  userId: string;
  mentorId: string;
  programId: string;
  preferences: string;
  learningGoals: string;
  skills: { name: string; level: SkillLevel }[];
  major?: string;
  university?: string;
}

export interface InternshipProgram {
  id: string;
  mentorId: string;
  title: string;
  description: string;
  role: string;
  startDate: string;
  endDate: string;
  durationWeeks: number;
  skillsToDevelop: string[];
  goals: string;
  skillsNeeded: string[];
  expectedOutcome: string;
  finalProject?: string;
  status: ProgramStatus;
  maxInterns: number;
  department: string;
  weeklyHours: number;
  additionalInstructions?: string;
}

export type ResourceKind =
  | "PDF"
  | "DOC"
  | "PPT"
  | "IMAGE"
  | "ZIP"
  | "LINK"
  | "OTHER";

/** Shared shape for program reference materials and task learning resources. */
export interface LearningResource {
  id: string;
  title: string;
  kind: ResourceKind;
  /** Display file name for uploads */
  fileName?: string;
  /** Primary open/download target (file URL when present, otherwise external link) */
  href: string;
  /** Optional external link retained alongside an uploaded file */
  externalUrl?: string;
}

export interface ReferenceMaterial extends LearningResource {
  programId: string;
}

export interface RoadmapTaskDraft {
  id: string;
  title: string;
  description: string;
  difficulty: string;
  estimatedTime: string;
  deliverable: string;
  successCriteria: string;
  source: TaskSource;
  requirementType: TaskRequirementType;
  dueDate?: string;
  assignedInternIds?: string[];
  priority?: string;
}

export interface RoadmapWeek {
  /** Present when loaded/saved via API */
  id?: string;
  weekNumber: number;
  weeklyFocus: string;
  weeklyLearningObjectives: string[];
  suggestedTasks: RoadmapTaskDraft[];
  expectedSkillsGained: string[];
  mentorNotes?: string;
}

export interface Roadmap {
  id: string;
  programId: string;
  title: string;
  summary: string;
  scope: RoadmapScope;
  status: RoadmapStatus;
  numberOfWeeks: number;
  weeks: RoadmapWeek[];
  assignedInternIds: string[];
  publishedAt?: string;
}

export interface Task {
  id: string;
  programId: string;
  roadmapId?: string;
  weekNumber: number;
  title: string;
  description: string;
  difficulty: string;
  estimatedTime: string;
  deliverable: string;
  successCriteria: string;
  priority?: string;
  source: TaskSource;
  requirementType: TaskRequirementType;
  defaultDeadline: string;
  resources: LearningResource[];
}

export interface TaskAssignment {
  id: string;
  taskId: string;
  taskTitle?: string;
  programId?: string;
  programTitle?: string;
  weekNumber?: number | null;
  internProfileId: string;
  internName?: string;
  status: TaskStatus;
  deadline: string;
  score?: number;
  mentorFeedback?: string;
  completedAt?: string;
}

export interface SubmissionFile {
  id: string;
  name: string;
  url: string;
}

export interface Submission {
  id: string;
  taskAssignmentId: string;
  writtenResponse?: string;
  files: SubmissionFile[];
  externalLink?: string;
  submissionVersion: number;
  internNotes?: string;
  submittedAt: string;
}

export interface WeeklyReport {
  id: string;
  internProfileId: string;
  programId: string;
  weekNumber: number;
  status: AiContentStatus;
  content: {
    performanceSummary: string;
    achievements: string[];
    learningProgress: string;
    productivityAnalysis: string;
    mentorFocusSuggestions: string[];
    recommendedFocusNextWeek: string;
  };
  /** Extra notes added by the mentor before/after editing the AI draft */
  additionalMentorNotes?: string;
  approvedAt?: string;
}

export interface FinalSummary {
  id: string;
  internProfileId: string;
  programId: string;
  status: AiContentStatus;
  content: {
    overallPerformanceSummary: string;
    learningJourney: string;
    mainAchievements: string[];
    goalAchievement: string;
    finalPerformanceSummary: string;
  };
    mentorFinalScore?: number;
  scoredWeeklyReportCount?: number;
  weekPerformance?: {
    weeks: Array<{
      week_number: number;
      weekly_score: number | null;
      completed_tasks: number;
      total_tasks: number;
      needs_revision: number;
      main_focus: string | null;
    }>;
  };
  mentorFinalComments?: string;
  /** Extra notes/context added by the mentor while editing */
  additionalMentorNotes?: string;
  pdfAvailable: boolean;
  approvedAt?: string;
}

export interface ActivityItem {
  id: string;
  type: string;
  description: string;
  timestamp: string;
  actorName: string;
}
