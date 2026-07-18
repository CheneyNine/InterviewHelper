export type InterviewStatus =
  | "GENERATING_QUESTIONS"
  | "QUESTIONS_READY"
  | "IN_PROGRESS"
  | "ANALYZING"
  | "COMPLETED"
  | "FAILED";

export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";

export interface CreateInterviewInput {
  job_title: string;
  job_description: string;
  job_requirements: string;
  interview_stage: string;
  question_count: number;
  locale: string;
}

export interface Interview {
  id: string;
  job_title?: string;
  job_description?: string;
  job_requirements?: string;
  interview_stage?: string;
  locale?: string;
  question_count?: number;
  status: InterviewStatus;
  created_at?: string;
  updated_at?: string;
}

export interface InterviewProjectSummary {
  id: string;
  job_title: string;
  interview_stage: string;
  status: InterviewStatus;
  question_count: number;
  answered_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface Question {
  id: string;
  interview_id: string;
  order: number;
  type: "behavioral" | "technical" | "situational";
  prompt: string;
  purpose?: string;
  competencies: string[];
  expected_signals: string[];
  follow_up_questions?: string[];
  reference_answer?: {
    positioning: string;
    logic_paths: Array<{ title: string; explanation: string; key_points: string[] }>;
    answer_outline: string[];
    evidence_to_include: string[];
    common_gaps: string[];
  };
  evaluation_rubric?: Array<{
    dimension: string;
    weight: number;
    description: string;
    strong_signals: string[];
    partial_signals: string[];
    missing_signals: string[];
  }>;
}

export interface Answer {
  id: string;
  question_id: string;
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  duration_ms: number;
  media_content_type: string;
  created_at: string;
}

export interface Job {
  id: string;
  type: "QUESTION_GENERATION" | "ANSWER_ANALYSIS";
  status: JobStatus;
  resource_id?: string;
  progress: number | null;
  error: { code: string; message: string } | null;
  created_at?: string;
  updated_at?: string;
}

export interface AnswerAnalysis {
  answer_id: string;
  transcript: {
    text: string;
    language: string;
    segments: Array<{ start_ms: number; end_ms: number; text: string; confidence: number }>;
  };
  content: {
    overall_score: number | null;
    dimension_scores: Record<string, number | null>;
    strengths: string[];
    improvements: string[];
    evidence: Array<{ claim: string; quote: string }>;
    dimension_analysis?: Array<{
      key: string;
      title: string;
      score: number | null;
      summary: string;
      evidence: string[];
      suggestions: string[];
      limitations: string[];
    }>;
    transcript_evaluation?: Record<string, unknown> | null;
    reference_comparison?: Record<string, unknown> | null;
  };
  question?: Question;
  reference_answer?: Question["reference_answer"];
  actual_answer?: string;
  delivery: {
    metrics: Record<string, number | null>;
    observations: Array<{
      code: string;
      start_ms: number;
      end_ms: number;
      confidence: number;
      message: string;
    }>;
    suggestions: string[];
    unavailable_reasons: string[];
  };
}

export interface InterviewReport {
  interview_id: string;
  summary: string;
  overall_score: number | null;
  top_strengths: string[];
  priority_improvements: string[];
  answer_analyses: Array<{ question_id: string; answer_id: string; analysis_url: string }>;
  disclaimer: string;
  dimension_scores?: Record<string, number | null>;
}

export interface ApiErrorShape {
  error?: { code?: string; message?: string; request_id?: string };
}
