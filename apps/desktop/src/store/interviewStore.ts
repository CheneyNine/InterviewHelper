import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AnswerAnalysis, Interview, InterviewReport, Job, Question } from "../types";

export type AppPhase = "welcome" | "generating" | "interview" | "analysis" | "report";

interface InterviewState {
  phase: AppPhase;
  permissionGranted: boolean;
  interview: Interview | null;
  questions: Question[];
  currentQuestionIndex: number;
  activeJob: Job | null;
  activeAnswerId: string | null;
  analyses: Record<string, AnswerAnalysis>;
  report: InterviewReport | null;
  idempotencyKeys: Record<string, string>;
  setPermissionGranted: (value: boolean) => void;
  startInterview: (interview: Interview, job: Job) => void;
  loadInterview: (interview: Interview, questions: Question[]) => void;
  beginAnalysis: (job: Job, answerId: string) => void;
  saveAnalysis: (questionId: string, analysis: AnswerAnalysis) => void;
  advance: () => void;
  showReport: (report: InterviewReport) => void;
  getIdempotencyKey: (questionId: string) => string;
  reset: () => void;
}

const initialState = {
  phase: "welcome" as AppPhase,
  permissionGranted: false,
  interview: null,
  questions: [],
  currentQuestionIndex: 0,
  activeJob: null,
  activeAnswerId: null,
  analyses: {},
  report: null,
  idempotencyKeys: {},
};

export const useInterviewStore = create<InterviewState>()(
  persist(
    (set, get) => ({
      ...initialState,
      setPermissionGranted: (permissionGranted) => set({ permissionGranted }),
      startInterview: (interview, activeJob) => set({
        interview,
        activeJob,
        phase: "generating",
        questions: [],
        currentQuestionIndex: 0,
        analyses: {},
        report: null,
      }),
      loadInterview: (interview, questions) => set({ interview, questions, phase: "interview", activeJob: null }),
      beginAnalysis: (activeJob, activeAnswerId) => set({ phase: "analysis", activeJob, activeAnswerId }),
      saveAnalysis: (questionId, analysis) => set((state) => ({
        analyses: { ...state.analyses, [questionId]: analysis },
      })),
      advance: () => set((state) => ({
        currentQuestionIndex: Math.min(state.currentQuestionIndex + 1, state.questions.length - 1),
        phase: "interview",
        activeJob: null,
        activeAnswerId: null,
      })),
      showReport: (report) => set({ report, phase: "report", activeJob: null }),
      getIdempotencyKey: (questionId) => {
        const existing = get().idempotencyKeys[questionId];
        if (existing) return existing;
        const key = crypto.randomUUID();
        set((state) => ({ idempotencyKeys: { ...state.idempotencyKeys, [questionId]: key } }));
        return key;
      },
      reset: () => set({ ...initialState, permissionGranted: get().permissionGranted }),
    }),
    {
      name: "interview-helper-session",
      partialize: (state) => ({
        phase: state.phase,
        permissionGranted: state.permissionGranted,
        interview: state.interview,
        questions: state.questions,
        currentQuestionIndex: state.currentQuestionIndex,
        activeJob: state.activeJob,
        activeAnswerId: state.activeAnswerId,
        analyses: state.analyses,
        report: state.report,
        idempotencyKeys: state.idempotencyKeys,
      }),
    },
  ),
);
