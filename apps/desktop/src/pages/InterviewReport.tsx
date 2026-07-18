import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Check, Flag, Plus, Trophy } from "lucide-react";
import { useEffect } from "react";
import { getInterviewReport } from "../lib/api";
import { useInterviewStore } from "../store/interviewStore";

export function InterviewReportPage() {
  const interview = useInterviewStore((state) => state.interview);
  const report = useInterviewStore((state) => state.report);
  const questions = useInterviewStore((state) => state.questions);
  const analyses = useInterviewStore((state) => state.analyses);
  const showReport = useInterviewStore((state) => state.showReport);
  const openAnalysis = useInterviewStore((state) => state.openAnalysis);
  const newProject = useInterviewStore((state) => state.newProject);

  const reportQuery = useQuery({
    queryKey: ["interview-report", interview?.id],
    queryFn: () => getInterviewReport(interview!.id),
    enabled: Boolean(interview) && !report,
    retry: false,
    refetchInterval: report ? false : 2000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (reportQuery.data) showReport(reportQuery.data);
  }, [reportQuery.data, showReport]);

  const activeReport = report || reportQuery.data;
  if (!activeReport) {
    return (
      <div className="center-page report-waiting">
        <span className="spinner" />
        <h1>回答已全部提交</h1>
        <p>总结页会在后端报告准备好后自动出现，你也可以先切换到侧栏中的其他项目。</p>
        {reportQuery.isError && <span className="muted">报告仍在生成，页面会自动重新获取。</span>}
      </div>
    );
  }

  const score = activeReport.overall_score === null ? null : Math.round(activeReport.overall_score * 100);
  const dimensionLabels: Record<string, string> = { visible_expression: "神情与镜头表现", content_and_fluency: "回答内容与流畅程度", tone_and_voice: "语气与声音表现", answer_structure: "回答结构与题目呈现", relevance: "题目相关性", technical_depth: "专业准确性与技术深度", evidence_and_contribution: "证据与个人贡献", role_fit: "岗位匹配度与业务理解" };

  return (
    <div className="report-page">
      <header className="report-hero">
        <div><div className="eyebrow"><Trophy size={15} /> 模拟面试已完成</div><h1>训练报告</h1><p>{activeReport.summary}</p></div>
        <div className="report-score"><strong>{score ?? "—"}</strong><span>综合内容表现</span><small>{score === null ? "指标不可用" : score >= 80 ? "表现扎实" : score >= 65 ? "基础良好" : "继续练习"}</small></div>
      </header>

      <section className="report-band">
        <div className="report-list strengths"><h2><Check size={19} />你的优势</h2>{activeReport.top_strengths.map((item) => <p key={item}>{item}</p>)}</div>
        <div className="report-list priorities"><h2><Flag size={19} />优先训练</h2>{activeReport.priority_improvements.map((item, index) => <p key={item}><span>{index + 1}</span>{item}</p>)}</div>
      </section>

      {activeReport.dimension_scores && <section className="report-band report-dimensions"><div className="report-list"><h2>四维度总览</h2>{Object.entries(dimensionLabels).map(([key, label]) => { const value = activeReport.dimension_scores?.[key]; return <p key={key}><span>{label}</span><strong>{value == null ? "—" : `${Math.round(value * 100)}分`}</strong></p>; })}</div></section>}

      <section className="answer-review">
        <div className="section-title"><div><span>逐题回顾</span><h2>点击题目查看对应分析</h2></div><strong>{activeReport.answer_analyses.length}/{questions.length} 已分析</strong></div>
        <div className="answer-table">
          {questions.map((question, index) => {
            const analysis = analyses[question.id];
            const value = analysis?.content.overall_score;
            const available = activeReport.answer_analyses.some((item) => item.question_id === question.id);
            return (
              <button className="answer-row" disabled={!available} key={question.id} onClick={() => openAnalysis(question.id)}>
                <span className="answer-index">{String(index + 1).padStart(2, "0")}</span>
                <span className="answer-copy"><strong>{question.prompt}</strong><span>{analysis?.content.strengths[0] ?? (available ? "查看内容、表达与证据分析" : "分析尚未返回")}</span></span>
                <strong className="answer-score">{value == null ? "查看" : Math.round(value * 100)}</strong>
                <ArrowUpRight size={17} />
              </button>
            );
          })}
        </div>
      </section>

      <footer className="report-footer">
        <p>{activeReport.disclaimer}</p>
        <button className="button button-primary" onClick={newProject}><Plus size={16} />新建面试项目</button>
      </footer>
    </div>
  );
}
