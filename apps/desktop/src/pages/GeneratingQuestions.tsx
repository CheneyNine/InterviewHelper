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
    refetchInterval: (state) => state.state.data?.status === "SUCCEEDED" ? false : 2000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (query.data?.status === "SUCCEEDED" && interview) {
      getInterview(interview.id).then((result) => loadInterview(result.interview, result.questions));
    }
  }, [interview, loadInterview, query.data?.status]);

  const progress = Math.max(8, Math.round((query.data?.progress ?? 0.08) * 100));

  return (
    <div className="center-page generating-page">
      <div className="generating-mark"><Sparkles size={32} /></div>
      <div className="eyebrow">正在准备你的模拟面试</div>
      <h1>从岗位描述中提炼关键能力</h1>
      <p>通常需要几秒钟。窗口切回前台时会自动刷新状态。</p>
      <div className="generation-progress"><span style={{ width: `${progress}%` }} /></div>
      <strong className="progress-number">{progress}%</strong>
      <div className="generation-steps">
        <div className="done"><Check size={17} /><span>读取岗位信息</span></div>
        <div className={progress > 45 ? "done" : "active"}><FileSearch size={17} /><span>识别核心能力</span></div>
        <div className={progress > 82 ? "active" : ""}><ListChecks size={17} /><span>生成结构化问题</span></div>
      </div>
      {query.isError && <div className="inline-error">问题生成状态暂时无法获取，将自动重试。</div>}
    </div>
  );
}
