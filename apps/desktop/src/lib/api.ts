import type {
  Answer,
  AnswerAnalysis,
  ApiErrorShape,
  CreateInterviewInput,
  Interview,
  InterviewProjectSummary,
  InterviewReport,
  Job,
  Question,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const REQUEST_TIMEOUT_MS = 15_000;
// Stub mode is opt-in so local integration uses the Core API by default.
export const usingStub = import.meta.env.VITE_USE_STUB === "true";

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const id = () => crypto.randomUUID();

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
  ) {
    super(message);
  }
}

function friendlyError(status: number, code: string, fallback: string) {
  const messages: Record<string, string> = {
    ANALYSIS_NOT_READY: "分析仍在进行，请稍候。",
    REPORT_NOT_READY: "整场报告正在汇总，请稍候。",
    INVALID_STATE: "当前会话状态不允许此操作，请刷新后重试。",
    MEDIA_TOO_LARGE: "录制文件超过上传限制，请缩短回答后重录。",
    UNSUPPORTED_MEDIA_TYPE: "当前录制格式不受支持，请更换设备或浏览器后重录。",
    MEDIA_UNREADABLE: "录制文件无法读取，请重新录制。",
    DEPENDENCY_UNAVAILABLE: "分析服务暂时不可用，本地录制仍保留，可稍后重试。",
    NETWORK_ERROR: "无法连接 Core API，请检查 Public API 地址和服务是否已启动。",
    METHOD_NOT_ALLOWED: "当前地址不是 InterviewHelper Core API，请检查 VITE_API_BASE_URL。",
    ROUTE_NOT_FOUND: "Core API 未提供该接口，请确认服务版本和 Public API 路径。",
    REQUEST_TIMEOUT: "Core API 请求超时，请确认 8000 端口服务已启动且 Interviewer 服务可用。",
  };
  return messages[code] ?? fallback ?? `请求失败 (${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, signal: controller.signal });
  } catch (cause) {
    const timedOut = cause instanceof DOMException && cause.name === "AbortError";
    const code = timedOut ? "REQUEST_TIMEOUT" : "NETWORK_ERROR";
    throw new ApiError(
      friendlyError(0, code, cause instanceof Error ? cause.message : "Network request failed"),
      0,
      code,
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiErrorShape & {
      detail?: { code?: string; message?: string };
    };
    const error = body.error ?? body.detail;
    const code = error?.code
      ?? (response.status === 404 ? "ROUTE_NOT_FOUND" : response.status === 405 ? "METHOD_NOT_ALLOWED" : "UNKNOWN_ERROR");
    throw new ApiError(friendlyError(response.status, code, error?.message ?? response.statusText), response.status, code);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const mockQuestions: Omit<Question, "interview_id">[] = [
  {
    id: "q-1",
    order: 1,
    type: "behavioral",
    prompt: "请介绍一个你主导解决的复杂问题。你当时如何判断优先级，最终结果怎样？",
    competencies: ["问题拆解", "主人翁意识"],
    expected_signals: ["明确个人行动", "说明判断依据", "量化最终影响"],
  },
  {
    id: "q-2",
    order: 2,
    type: "technical",
    prompt: "面对一个响应时间持续升高的线上系统，你会如何定位瓶颈并验证优化效果？",
    competencies: ["技术深度", "系统思维"],
    expected_signals: ["建立指标基线", "提出可验证假设", "说明取舍"],
  },
  {
    id: "q-3",
    order: 3,
    type: "situational",
    prompt: "项目临近交付时，关键需求突然变化，而团队意见不一致。你会怎么推进？",
    competencies: ["沟通协作", "决策能力"],
    expected_signals: ["澄清共同目标", "识别风险", "形成可执行方案"],
  },
  {
    id: "q-4",
    order: 4,
    type: "behavioral",
    prompt: "讲述一次你的方案没有达到预期的经历。你如何复盘，又做了哪些调整？",
    competencies: ["复盘能力", "成长意识"],
    expected_signals: ["坦诚说明责任", "提炼根因", "展示后续改变"],
  },
  {
    id: "q-5",
    order: 5,
    type: "situational",
    prompt: "如果入职后的第一个月只能推动一项改进，你会如何选择并获得团队支持？",
    competencies: ["影响力", "业务理解"],
    expected_signals: ["先调研后判断", "关联业务价值", "小步验证"],
  },
];

const mockJobStarts = new Map<string, number>();
let mockInterview: Interview | null = null;
let mockAnswers: Answer[] = [];

function makeJob(type: Job["type"], resourceId?: string): Job {
  const job: Job = {
    id: id(),
    type,
    status: "QUEUED",
    resource_id: resourceId,
    progress: 0,
    error: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  mockJobStarts.set(job.id, Date.now());
  return job;
}

/**
 * GET /interviews
 * 为左侧项目栏获取当前用户创建过的面试项目。后端应按 updated_at 倒序返回，
 * 每项只包含列表展示所需的摘要，不应携带 JD 全文或分析详情。
 */
export async function listInterviews(): Promise<InterviewProjectSummary[]> {
  if (!usingStub) {
    const result = await request<{ interviews: InterviewProjectSummary[] }>("/interviews");
    return result.interviews;
  }
  if (!mockInterview) return [];
  return [{
    id: mockInterview.id,
    job_title: mockInterview.job_title || "未命名岗位",
    interview_stage: mockInterview.interview_stage || "模拟面试",
    status: mockInterview.status,
    question_count: mockInterview.question_count || 0,
    answered_count: mockAnswers.length,
    created_at: mockInterview.created_at,
    updated_at: mockInterview.updated_at || mockInterview.created_at,
  }];
}

/** POST /interviews：创建一个面试项目并启动问题生成 Job。 */
export async function createInterview(input: CreateInterviewInput) {
  if (!usingStub) {
    return request<{ interview: Interview; job: Job }>("/interviews", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": id() },
      body: JSON.stringify(input),
    });
  }
  await wait(650);
  mockInterview = {
    id: id(),
    ...input,
    status: "GENERATING_QUESTIONS",
    created_at: new Date().toISOString(),
  };
  mockAnswers = [];
  return { interview: mockInterview, job: makeJob("QUESTION_GENERATION", mockInterview.id) };
}

/**
 * GET /interviews/{interview_id}
 * 切换侧栏项目或恢复应用时，读取会话、题目和已提交答案，用于还原答题进度。
 */
export async function getInterview(interviewId: string) {
  if (!usingStub) {
    return request<{ interview: Interview; questions: Question[]; answers: Answer[] }>(`/interviews/${interviewId}`);
  }
  await wait(250);
  if (!mockInterview || mockInterview.id !== interviewId) {
    mockInterview = { id: interviewId, status: "QUESTIONS_READY" };
  }
  mockInterview = { ...mockInterview, status: mockAnswers.length ? "IN_PROGRESS" : "QUESTIONS_READY" };
  return {
    interview: mockInterview,
    questions: Array.from({ length: mockInterview.question_count ?? 5 }, (_, index) => {
      const question = mockQuestions[index % mockQuestions.length];
      return {
        ...question,
        id: `q-${index + 1}`,
        order: index + 1,
        interview_id: interviewId,
        purpose: question.purpose ?? "验证候选人能否结合岗位要求，清楚说明判断、行动和结果。",
        follow_up_questions: question.follow_up_questions ?? ["你当时最大的技术权衡是什么？"],
        reference_answer: question.reference_answer ?? {
          positioning: "先明确目标和约束，再说明个人行动、验证方式与结果。",
          logic_paths: [{ title: "问题拆解", explanation: "围绕目标、约束和验证路径组织回答。", key_points: ["目标", "约束", "验证"] }],
          answer_outline: ["背景与目标", "行动与权衡", "验证与结果", "复盘"],
          evidence_to_include: ["个人具体行动", "量化结果"],
          common_gaps: ["只讲团队行为，没有说明个人贡献"],
        },
        evaluation_rubric: question.evaluation_rubric ?? [],
      };
    }),
    answers: mockAnswers,
  };
}

/** GET /jobs/{job_id}：每 2 秒查询问题生成或回答分析的后端任务进度。 */
export async function getJob(jobId: string): Promise<Job> {
  if (!usingStub) return request<Job>(`/jobs/${jobId}`);
  await wait(220);
  if (!mockJobStarts.has(jobId)) mockJobStarts.set(jobId, Date.now());
  const elapsed = Date.now() - mockJobStarts.get(jobId)!;
  const progress = Math.min(elapsed / 4200, 1);
  return {
    id: jobId,
    type: "ANSWER_ANALYSIS",
    status: progress >= 1 ? "SUCCEEDED" : progress > 0.18 ? "RUNNING" : "QUEUED",
    progress,
    error: null,
    updated_at: new Date().toISOString(),
  };
}

/**
 * POST /questions/{question_id}/answers
 * 用户确认后上传本题音视频；同一题重试必须复用 idempotencyKey，避免重复 Answer。
 */
export async function uploadAnswer(
  questionId: string,
  blob: Blob,
  durationMs: number,
  idempotencyKey: string,
  onProgress: (progress: number) => void,
) {
  if (usingStub) {
    for (const progress of [0.08, 0.24, 0.47, 0.72, 0.91, 1]) {
      await wait(180);
      onProgress(progress);
    }
    const answer: Answer = {
      id: id(),
      question_id: questionId,
      status: "PROCESSING",
      duration_ms: durationMs,
      media_content_type: blob.type || "video/webm",
      created_at: new Date().toISOString(),
    };
    mockAnswers.push(answer);
    return { answer, job: makeJob("ANSWER_ANALYSIS", answer.id) };
  }

  const form = new FormData();
  form.append("media", blob, `answer-${questionId}.webm`);
  form.append("duration_ms", String(durationMs));
  form.append("recorded_at", new Date().toISOString());

  return new Promise<{ answer: Answer; job: Job }>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/questions/${questionId}/answers`);
    xhr.setRequestHeader("Idempotency-Key", idempotencyKey);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      const body = JSON.parse(xhr.responseText || "{}") as { answer: Answer; job: Job } & ApiErrorShape;
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else {
        const code = body.error?.code ?? "UNKNOWN_ERROR";
        reject(new ApiError(friendlyError(xhr.status, code, body.error?.message ?? xhr.statusText), xhr.status, code));
      }
    };
    xhr.onerror = () => reject(new ApiError("网络连接中断，录制仍保留在本地，可重新上传。", 0, "NETWORK_ERROR"));
    xhr.send(form);
  });
}

/** GET /answers/{answer_id}/analysis：在总报告中点开某道题时获取该题完整分析。 */
export async function getAnswerAnalysis(answerId: string): Promise<AnswerAnalysis> {
  if (!usingStub) return request<AnswerAnalysis>(`/answers/${answerId}/analysis`);
  await wait(300);
  return {
    answer_id: answerId,
    transcript: {
      text: "我先把问题拆成影响范围、时间窗口和可回滚性三个部分，随后与团队对齐优先级，并通过小范围验证确认方案。最终将处理时间缩短了约三成。",
      language: "zh-CN",
      segments: [],
    },
    content: {
      overall_score: 0.78,
      dimension_scores: { visible_expression: 0.78, content_and_fluency: 0.84, tone_and_voice: 0.72, answer_structure: 0.81, relevance: 0.86, technical_depth: 0.74, evidence_and_contribution: 0.72, role_fit: 0.68 },
      strengths: ["回答紧扣问题，个人行动表达清楚", "有明确的问题拆解与验证过程"],
      improvements: ["补充结果对应的业务指标", "开头先用一句话概括最终结论"],
      evidence: [{ claim: "行动路径清晰", quote: "我先把问题拆成影响范围、时间窗口和可回滚性三个部分" }],
    },
    delivery: {
      metrics: { words_per_minute: 156, pause_ratio: 0.17, filler_count: 4, offscreen_face_ratio: null },
      observations: [{
        code: "FAST_SPEECH_SEGMENT",
        start_ms: 18000,
        end_ms: 27000,
        confidence: 0.82,
        message: "说明行动细节时语速略快，可以在关键步骤之间稍作停顿。",
      }],
      suggestions: ["说完结论后停顿一秒，再进入背景和行动细节。"],
      unavailable_reasons: ["当前设备未稳定检测到视线方向，因此未提供离屏比例。"],
    },
  };
}

/** GET /interviews/{interview_id}/report：所有题目分析完成后获取整场聚合报告。 */
export async function getInterviewReport(interviewId: string): Promise<InterviewReport> {
  if (!usingStub) return request<InterviewReport>(`/interviews/${interviewId}/report`);
  await wait(600);
  return {
    interview_id: interviewId,
    summary: "你的回答整体聚焦岗位要求，善于拆解问题并交代个人行动。下一步可把结果量化和开场结论练得更稳定，让面试官更快抓住价值。",
    overall_score: 0.78,
    dimension_scores: { visible_expression: 0.78, content_and_fluency: 0.84, tone_and_voice: 0.72, answer_structure: 0.81, relevance: 0.86, technical_depth: 0.74, evidence_and_contribution: 0.72, role_fit: 0.68 },
    top_strengths: ["个人职责与行动边界清楚", "回答结构完整，能说明判断依据", "复盘意识和协作意识突出"],
    priority_improvements: ["用具体数字说明影响", "先结论后背景，压缩铺垫", "关键步骤之间增加短暂停顿"],
    answer_analyses: mockAnswers.map((answer) => ({
      question_id: answer.question_id,
      answer_id: answer.id,
      analysis_url: `/api/v1/answers/${answer.id}/analysis`,
    })),
    disclaimer: "这些结果是训练建议，不是心理、医学或招聘结论。",
  };
}

/** DELETE /interviews/{interview_id}：删除项目、关联回答、分析结果和原始媒体。 */
export async function deleteInterview(interviewId: string): Promise<void> {
  if (!usingStub) {
    await request<void>(`/interviews/${interviewId}`, { method: "DELETE" });
    return;
  }
  if (mockInterview?.id === interviewId) {
    mockInterview = null;
    mockAnswers = [];
  }
}
