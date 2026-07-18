import { useQuery } from "@tanstack/react-query";
import { Check, FileSearch, ListChecks, Sparkles } from "lucide-react";
import { useEffect } from "react";
import { getInterview, getJob } from "../lib/api";
import { useInterviewStore } from "../store/interviewStore";

export function GeneratingQuestions() {
  const interview = useInterviewStore((state) => state.interview);
  const job = useInterviewStore((state) => state.activeJob);
  const loadInterview = useInterviewStore((state) => state.loadInterview);

  const query = useQuery({
    queryKey: ["job", job?.id],
    queryFn: () => getJob(job!.id),
    enabled: Boolean(job),
    refetchInterval: (state) => {
      const status = state.state.data?.status;
      return status === "SUCCEEDED" || status === "FAILED" ? false : 2000;
    },
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (query.data?.status === "SUCCEEDED" && interview) {
      getInterview(interview.id).then((result) => loadInterview(result.interview, result.questions));
    }
  }, [interview, loadInterview, query.data?.status]);

  const jobState = query.data ?? job;
  const backendProgress = typeof jobState?.progress === "number"
    ? Math.min(1, Math.max(0, jobState.progress))
    : null;
  const progress = backendProgress === null ? null : Math.round(backendProgress * 100);
  const failed = jobState?.status === "FAILED";
  const stageProgress = backendProgress ?? 0;

  return (
    <div className="center-page generating-page">
      <div className="generating-mark"><Sparkles size={32} /></div>
      <div className="eyebrow">正在准备你的模拟面试</div>
      <h1>从岗位描述中提炼关键能力</h1>
      <p>通常需要几秒钟。窗口切回前台时会自动刷新状态。</p>
      <div
        className={`generation-progress ${progress === null ? "indeterminate" : ""}`}
        role="progressbar"
        aria-label="问题生成进度"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress ?? undefined}
      >
        <span style={progress === null ? undefined : { width: `${progress}%` }} />
      </div>
      <strong className="progress-number">{progress === null ? "处理中" : `${progress}%`}</strong>
      <div className="generation-steps">
        <div className="done"><Check size={17} /><span>读取岗位信息</span></div>
        <div className={stageProgress >= 0.45 ? "done" : "active"}><FileSearch size={17} /><span>识别核心能力</span></div>
        <div className={stageProgress >= 1 ? "done" : stageProgress >= 0.82 ? "active" : ""}><ListChecks size={17} /><span>生成结构化问题</span></div>
      </div>
      {failed && <div className="inline-error">{jobState?.error?.message ?? "问题生成失败，请返回后重试。"}</div>}
      {query.isError && !failed && <div className="inline-error">问题生成状态暂时无法获取，将自动重试。</div>}
    </div>
  );
}
