import { Check, Lightbulb, ListChecks } from "lucide-react";
import { AnswerRecorder } from "../components/AnswerRecorder";
import { useInterviewStore } from "../store/interviewStore";

const typeLabels = { behavioral: "行为题", technical: "技术题", situational: "情景题" };

export function InterviewPage() {
  const questions = useInterviewStore((state) => state.questions);
  const currentIndex = useInterviewStore((state) => state.currentQuestionIndex);
  const analyses = useInterviewStore((state) => state.analyses);
  const question = questions[currentIndex];

  if (!question) return <div className="center-page">正在恢复面试会话…</div>;

  return (
    <div className="interview-layout">
      <aside className="question-rail">
        <div className="rail-heading"><ListChecks size={17} /><span>问题列表</span><strong>{currentIndex + 1}/{questions.length}</strong></div>
        <div className="question-list">
          {questions.map((item, index) => (
            <div className={`question-item ${index === currentIndex ? "current" : ""} ${analyses[item.id] ? "done" : ""}`} key={item.id}>
              <span>{analyses[item.id] ? <Check size={14} /> : index + 1}</span>
              <div><small>{typeLabels[item.type]}</small><p>{item.prompt}</p></div>
            </div>
          ))}
        </div>
        <div className="rail-tip"><Lightbulb size={16} /><p><strong>回答提示</strong>用“情境—任务—行动—结果”组织经历，重点讲清你的个人行动。</p></div>
      </aside>

      <section className="interview-main">
        <div className="question-header">
          <div><span className="question-number">问题 {question.order}</span><span className="question-type">{typeLabels[question.type]}</span></div>
          <h1>{question.prompt}</h1>
          {question.purpose && <p className="question-purpose">{question.purpose}</p>}
          <div className="competency-row">
            <span>考察维度</span>
            {question.competencies.map((item) => <i key={item}>{item}</i>)}
          </div>
        </div>
        <AnswerRecorder key={question.id} question={question} />
      </section>
    </div>
  );
}
