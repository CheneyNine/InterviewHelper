import { useQuery } from "@tanstack/react-query";
import { BarChart3, Check, Clock3, MessageSquareQuote, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { getAnswerAnalysis, getInterviewReport, getJob } from "../lib/api";
import { useInterviewStore } from "../store/interviewStore";
import type { AnswerAnalysis as AnswerAnalysisType } from "../types";

const dimensionLabels: Record<string, string> = {
  relevance: "相关性",
  specificity: "具体程度",
  structure: "结构表达",
  impact: "结果影响",
};

function ScoreRing({ score }: { score: number | null }) {
  const value = score === null ? 0 : Math.round(score * 100);
  return <div className="score-ring" style={{ "--score": `${value * 3.6}deg` } as React.CSSProperties}><strong>{score === null ? "—" : value}</strong><span>内容得分</span></div>;
}

export function AnswerAnalysisPage() {
  const job = useInterviewStore((state) => state.activeJob);
  const answerId = useInterviewStore((state) => state.activeAnswerId);
  const interview = useInterviewStore((state) => state.interview);
  const questions = useInterviewStore((state) => state.questions);
  const currentIndex = useInterviewStore((state) => state.currentQuestionIndex);
  const saveAnalysis = useInterviewStore((state) => state.saveAnalysis);
  const advance = useInterviewStore((state) => state.advance);
  const showReport = useInterviewStore((state) => state.showReport);
  const [analysis, setAnalysis] = useState<AnswerAnalysisType | null>(null);
  const [loadingResult, setLoadingResult] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const question = questions[currentIndex];

  const jobQuery = useQuery({
    queryKey: ["job", job?.id],
    queryFn: () => getJob(job!.id),
    enabled: Boolean(job) && !analysis,
    refetchInterval: (state) => state.state.data?.status === "SUCCEEDED" ? false : 2000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (jobQuery.data?.status !== "SUCCEEDED" || !answerId || !question || loadingResult) return;
    setLoadingResult(true);
    getAnswerAnalysis(answerId)
      .then((result) => {
        setAnalysis(result);
        saveAnalysis(question.id, result);
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "分析结果读取失败。"))
      .finally(() => setLoadingResult(false));
  }, [answerId, jobQuery.data?.status, loadingResult, question, saveAnalysis]);

  const continueFlow = async () => {
    if (currentIndex < questions.length - 1) {
      advance();
      return;
    }
    if (!interview) return;
    try {
      const report = await getInterviewReport(interview.id);
      showReport(report);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "报告仍在生成，请稍后重试。");
    }
  };

  if (!analysis) {
    const progress = Math.max(5, Math.round((jobQuery.data?.progress ?? 0.05) * 100));
    return (
      <div className="center-page analysis-loading">
        <div className="analysis-orbit"><span /><Sparkles size={28} /></div>
        <div className="eyebrow">第 {currentIndex + 1} 题已安全上传</div>
        <h1>正在拆解这段回答</h1>
        <p>我们会分别分析内容结构与表达节奏，不推断情绪或人格。</p>
        <div className="analysis-pipeline">
          <div className={progress > 20 ? "done" : "active"}><Check size={16} /><span>媒体校验</span></div>
          <div className={progress > 55 ? "done" : "active"}><MessageSquareQuote size={16} /><span>内容转写</span></div>
          <div className={progress > 85 ? "done" : "active"}><BarChart3 size={16} /><span>反馈生成</span></div>
        </div>
        <div className="generation-progress wide"><span style={{ width: `${progress}%` }} /></div>
        <span className="muted"><Clock3 size={14} />通常在 10 秒内完成</span>
        {(jobQuery.isError || error) && <div className="inline-error">{error ?? "状态暂时无法获取，窗口保持打开后会自动重试。"}</div>}
      </div>
    );
  }

  return (
    <div className="analysis-page">
      <header className="analysis-header">
        <div><div className="eyebrow"><Check size={15} /> 第 {currentIndex + 1} 题分析完成</div><h1>回答反馈</h1><p>{question.prompt}</p></div>
        <ScoreRing score={analysis.content.overall_score} />
      </header>

      <div className="analysis-grid">
        <section className="analysis-section dimension-section">
          <h2>内容维度</h2>
          {Object.entries(analysis.content.dimensions).map(([key, value]) => (
            <div className="dimension-row" key={key}>
              <span>{dimensionLabels[key] ?? key}</span>
              <div><i style={{ width: `${(value ?? 0) * 100}%` }} /></div>
              <strong>{value === null ? "—" : Math.round(value * 100)}</strong>
            </div>
          ))}
        </section>

        <section className="analysis-section">
          <h2>表达概览</h2>
          <div className="metric-grid">
            <div><strong>{analysis.delivery.metrics.words_per_minute ?? "—"}</strong><span>字/分钟</span></div>
            <div><strong>{analysis.delivery.metrics.pause_ratio === null ? "—" : `${Math.round((analysis.delivery.metrics.pause_ratio ?? 0) * 100)}%`}</strong><span>停顿占比</span></div>
            <div><strong>{analysis.delivery.metrics.filler_count ?? "—"}</strong><span>填充词</span></div>
          </div>
          {analysis.delivery.unavailable_reasons.map((reason) => <p className="unavailable" key={reason}>{reason}</p>)}
        </section>

        <section className="analysis-section feedback-section">
          <div className="feedback-column strengths"><h2>做得好的地方</h2>{analysis.content.strengths.map((item) => <p key={item}><Check size={16} />{item}</p>)}</div>
          <div className="feedback-column improvements"><h2>下一步这样练</h2>{analysis.content.improvements.map((item, index) => <p key={item}><span>{index + 1}</span>{item}</p>)}</div>
        </section>

        <section className="analysis-section transcript-section">
          <h2><MessageSquareQuote size={18} />转写与证据</h2>
          <blockquote>“{analysis.transcript.text}”</blockquote>
          {analysis.content.evidence.map((item) => <div className="evidence" key={item.claim}><strong>{item.claim}</strong><span>“{item.quote}”</span></div>)}
        </section>
      </div>
      {error && <div className="inline-error">{error}</div>}
      <div className="analysis-footer"><span>这些反馈是训练建议，不是招聘结论。</span><button className="button button-primary" onClick={continueFlow}>{currentIndex < questions.length - 1 ? "继续下一题" : "查看整场报告"}</button></div>
    </div>
  );
}
