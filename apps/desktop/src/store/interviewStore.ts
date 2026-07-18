import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Answer, AnswerAnalysis, Interview, InterviewProjectSummary, InterviewReport, Job, Question } from "../types";

export type AppPhase = "welcome" | "generating" | "interview" | "analysis" | "report" | "answer-detail";

interface InterviewState {
  phase: AppPhase;
  permissionGranted: boolean;
  projects: InterviewProjectSummary[];
  interview: Interview | null;
  questions: Question[];
  currentQuestionIndex: number;
  activeJob: Job | null;
  activeAnswerId: string | null;
  analyses: Record<string, AnswerAnalysis>;
  report: InterviewReport | null;
  selectedAnalysisQuestionId: string | null;
  idempotencyKeys: Record<string, string>;
  setPermissionGranted: (value: boolean) => void;
  setProjects: (projects: InterviewProjectSummary[]) => void;
  startInterview: (interview: Interview, job: Job) => void;
  loadInterview: (interview: Interview, questions: Question[], answers?: Answer[]) => void;
  beginAnalysis: (job: Job, answerId: string) => void;
  saveAnalysis: (questionId: string, analysis: AnswerAnalysis) => void;
  advance: () => void;
  showReport: (report: InterviewReport) => void;
  openAnalysis: (questionId: string) => void;
  backToReport: () => void;
  getIdempotencyKey: (questionId: string) => string;
  newProject: () => void;
  reset: () => void;
}

const initialSession = {
  phase: "welcome" as AppPhase,
  interview: null,
  questions: [],
  currentQuestionIndex: 0,
  activeJob: null,
  activeAnswerId: null,
  analyses: {},
  report: null,
  selectedAnalysisQuestionId: null,
  idempotencyKeys: {},
};

function toProject(interview: Interview, answeredCount = 0, existing?: InterviewProjectSummary): InterviewProjectSummary {
  return {
    id: interview.id,
    job_title: interview.job_title || existing?.job_title || "未命名岗位",
    interview_stage: interview.interview_stage || existing?.interview_stage || "模拟面试",
    status: interview.status,
    question_count: interview.question_count || existing?.question_count || 0,
    answered_count: Math.max(answeredCount, existing?.answered_count || 0),
    created_at: interview.created_at || existing?.created_at,
    updated_at: interview.updated_at || new Date().toISOString(),
  };
}

function mergeProjects(current: InterviewProjectSummary[], incoming: InterviewProjectSummary[]) {
  const merged = new Map(current.map((project) => [project.id, project]));
  incoming.forEach((project) => merged.set(project.id, { ...merged.get(project.id), ...project }));
  return [...merged.values()].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
}

export const useInterviewStore = create<InterviewState>()(
  persist(
    (set, get) => ({
      ...initialSession,
      permissionGranted: false,
      projects: [],
      setPermissionGranted: (permissionGranted) => set({ permissionGranted }),
      setProjects: (projects) => set((state) => ({ projects: mergeProjects(state.projects, projects) })),
      startInterview: (interview, activeJob) => set((state) => ({
        ...initialSession,
        interview,
        activeJob,
        phase: "generating",
        projects: mergeProjects(state.projects, [toProject(interview)]),
      })),
      loadInterview: (interview, questions, answers = []) => set((state) => {
        const answeredIds = new Set(answers.map((answer) => answer.question_id));
        const nextQuestionIndex = questions.findIndex((question) => !answeredIds.has(question.id));
        return {
          ...initialSession,
          interview,
          questions,
          currentQuestionIndex: nextQuestionIndex < 0 ? Math.max(questions.length - 1, 0) : nextQuestionIndex,
          phase: "interview",
          projects: mergeProjects(state.projects, [toProject(interview, answers.length, state.projects.find((item) => item.id === interview.id))]),
        };
      }),
      beginAnalysis: (activeJob, activeAnswerId) => set((state) => {
        const isLastQuestion = state.currentQuestionIndex >= state.questions.length - 1;
        const interview = state.interview ? {
          ...state.interview,
          status: isLastQuestion ? "ANALYZING" as const : "IN_PROGRESS" as const,
          updated_at: new Date().toISOString(),
        } : null;
        const projects = interview ? mergeProjects(state.projects, [toProject(
          interview,
          state.currentQuestionIndex + 1,
          state.projects.find((item) => item.id === interview.id),
        )]) : state.projects;
        if (isLastQuestion) {
          return { phase: "report", interview, activeJob, activeAnswerId, report: null, projects };
        }
        return {
          interview,
          currentQuestionIndex: state.currentQuestionIndex + 1,
          phase: "interview",
          activeJob: null,
          activeAnswerId: null,
          projects,
        };
      }),
      saveAnalysis: (questionId, analysis) => set((state) => ({
        analyses: { ...state.analyses, [questionId]: analysis },
        projects: state.interview ? mergeProjects(state.projects, [toProject(
          state.interview,
          Object.keys({ ...state.analyses, [questionId]: analysis }).length,
          state.projects.find((item) => item.id === state.interview?.id),
        )]) : state.projects,
      })),
      advance: () => set((state) => ({
        currentQuestionIndex: Math.min(state.currentQuestionIndex + 1, state.questions.length - 1),
        phase: "interview",
        activeJob: null,
        activeAnswerId: null,
      })),
      showReport: (report) => set((state) => ({
        report,
        phase: "report",
        activeJob: null,
        activeAnswerId: null,
        selectedAnalysisQuestionId: null,
        projects: state.interview ? mergeProjects(state.projects, [{
          ...toProject({ ...state.interview, status: "COMPLETED" }, state.questions.length),
          status: "COMPLETED",
        }]) : state.projects,
      })),
      openAnalysis: (selectedAnalysisQuestionId) => set({ selectedAnalysisQuestionId, phase: "answer-detail" }),
      backToReport: () => set({ selectedAnalysisQuestionId: null, phase: "report" }),
      getIdempotencyKey: (questionId) => {
        const existing = get().idempotencyKeys[questionId];
        if (existing) return existing;
        const key = crypto.randomUUID();
        set((state) => ({ idempotencyKeys: { ...state.idempotencyKeys, [questionId]: key } }));
        return key;
      },
      newProject: () => set((state) => ({ ...initialSession, permissionGranted: state.permissionGranted, projects: state.projects })),
      reset: () => get().newProject(),
    }),
    {
      name: "interview-helper-session",
      partialize: (state) => ({
        phase: state.phase,
        permissionGranted: state.permissionGranted,
        projects: state.projects,
        interview: state.interview,
        questions: state.questions,
        currentQuestionIndex: state.currentQuestionIndex,
        activeJob: state.activeJob,
        activeAnswerId: state.activeAnswerId,
        analyses: state.analyses,
        report: state.report,
        selectedAnalysisQuestionId: state.selectedAnalysisQuestionId,
        idempotencyKeys: state.idempotencyKeys,
      }),
    },
  ),
);
