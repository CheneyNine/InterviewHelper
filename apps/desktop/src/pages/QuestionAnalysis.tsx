import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Check, MessageSquareQuote } from "lucide-react";
import { useEffect } from "react";
import { getAnswerAnalysis } from "../lib/api";
import { useInterviewStore } from "../store/interviewStore";

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

export function QuestionAnalysisPage() {
  const questionId = useInterviewStore((state) => state.selectedAnalysisQuestionId);
  const questions = useInterviewStore((state) => state.questions);
  const report = useInterviewStore((state) => state.report);
  const cachedAnalysis = useInterviewStore((state) => questionId ? state.analyses[questionId] : undefined);
  const saveAnalysis = useInterviewStore((state) => state.saveAnalysis);
  const backToReport = useInterviewStore((state) => state.backToReport);
  const question = questions.find((item) => item.id === questionId);
  const answerId = report?.answer_analyses.find((item) => item.question_id === questionId)?.answer_id;

  const query = useQuery({
    queryKey: ["answer-analysis", answerId],
    queryFn: () => getAnswerAnalysis(answerId!),
    enabled: Boolean(answerId) && !cachedAnalysis,
    retry: 2,
  });

  useEffect(() => {
    if (questionId && query.data) saveAnalysis(questionId, query.data);
  }, [query.data, questionId, saveAnalysis]);

  const analysis = cachedAnalysis || query.data;
  if (!question || !answerId) {
    return <div className="center-page"><div className="inline-error">这道题的分析索引尚未由后端返回。</div><button className="button button-secondary" onClick={backToReport}><ArrowLeft size={16} />返回总报告</button></div>;
  }
  if (!analysis) {
    return <div className="center-page"><span className="spinner" /><h1>读取单题分析</h1><p>正在从 Core API 获取这道题的完整反馈。</p>{query.isError && <div className="inline-error">分析暂时无法读取，请返回后重试。</div>}<button className="button button-secondary" onClick={backToReport}><ArrowLeft size={16} />返回总报告</button></div>;
  }

  return (
    <div className="analysis-page">
      <button className="back-link" onClick={backToReport}><ArrowLeft size={16} />返回整场报告</button>
      <header className="analysis-header">
        <div><div className="eyebrow"><Check size={15} /> 第 {question.order} 题分析</div><h1>回答反馈</h1><p>{question.prompt}</p></div>
        <ScoreRing score={analysis.content.overall_score} />
      </header>

      <div className="analysis-grid">
        <section className="analysis-section dimension-section">
          <h2>内容维度</h2>
          {Object.entries(analysis.content.dimensions).map(([key, value]) => (
            <div className="dimension-row" key={key}><span>{dimensionLabels[key] ?? key}</span><div><i style={{ width: `${(value ?? 0) * 100}%` }} /></div><strong>{value === null ? "—" : Math.round(value * 100)}</strong></div>
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
      <div className="analysis-footer"><span>这些反馈是训练建议，不是招聘结论。</span><button className="button button-primary" onClick={backToReport}>返回整场报告</button></div>
    </div>
  );
}
