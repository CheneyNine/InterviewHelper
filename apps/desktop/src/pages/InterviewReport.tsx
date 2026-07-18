import { ArrowUpRight, Check, Flag, RotateCcw, Trophy } from "lucide-react";
import { useInterviewStore } from "../store/interviewStore";

export function InterviewReportPage() {
  const report = useInterviewStore((state) => state.report);
  const questions = useInterviewStore((state) => state.questions);
  const analyses = useInterviewStore((state) => state.analyses);
  const reset = useInterviewStore((state) => state.reset);

  if (!report) return <div className="center-page">正在汇总训练报告…</div>;
  const score = report.overall_content_score === null ? null : Math.round(report.overall_content_score * 100);

  return (
    <div className="report-page">
      <header className="report-hero">
        <div><div className="eyebrow"><Trophy size={15} /> 模拟面试已完成</div><h1>训练报告</h1><p>{report.summary}</p></div>
        <div className="report-score"><strong>{score ?? "—"}</strong><span>综合内容表现</span><small>{score === null ? "指标不可用" : score >= 80 ? "表现扎实" : score >= 65 ? "基础良好" : "继续练习"}</small></div>
      </header>

      <section className="report-band">
        <div className="report-list strengths"><h2><Check size={19} />你的优势</h2>{report.top_strengths.map((item) => <p key={item}>{item}</p>)}</div>
        <div className="report-list priorities"><h2><Flag size={19} />优先训练</h2>{report.priority_improvements.map((item, index) => <p key={item}><span>{index + 1}</span>{item}</p>)}</div>
      </section>

      <section className="answer-review">
        <div className="section-title"><div><span>逐题回顾</span><h2>看见每一次回答的进步空间</h2></div><strong>{Object.keys(analyses).length}/{questions.length} 已分析</strong></div>
        <div className="answer-table">
          {questions.map((question, index) => {
            const analysis = analyses[question.id];
            const value = analysis?.content.overall_score;
            return (
              <div className="answer-row" key={question.id}>
                <span className="answer-index">{String(index + 1).padStart(2, "0")}</span>
                <div className="answer-copy"><strong>{question.prompt}</strong><span>{analysis?.content.strengths[0] ?? "分析结果已归入整场总结"}</span></div>
                <strong className="answer-score">{value == null ? "—" : Math.round(value * 100)}</strong>
                <ArrowUpRight size={17} />
              </div>
            );
          })}
        </div>
      </section>

      <footer className="report-footer">
        <p>{report.disclaimer}</p>
        <button className="button button-primary" onClick={reset}><RotateCcw size={16} />开始新的模拟面试</button>
      </footer>
    </div>
  );
}
