import { BrainCircuit, CircleDot, RotateCcw } from "lucide-react";
import type { PropsWithChildren } from "react";
import { useInterviewStore } from "../store/interviewStore";

const phaseOrder = ["generating", "interview", "analysis", "report"];
const labels = ["生成问题", "模拟面试", "逐题分析", "训练报告"];

export function AppShell({ children }: PropsWithChildren) {
  const phase = useInterviewStore((state) => state.phase);
  const reset = useInterviewStore((state) => state.reset);
  const current = phase === "welcome" ? -1 : phaseOrder.indexOf(phase);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark"><BrainCircuit size={20} /></span><strong>InterviewHelper</strong></div>
        {phase !== "welcome" && (
          <nav className="steps" aria-label="面试进度">
            {labels.map((label, index) => (
              <div className={`step ${index <= current ? "active" : ""}`} key={label}>
                <CircleDot size={14} /><span>{label}</span>
              </div>
            ))}
          </nav>
        )}
        <button className="icon-button" onClick={reset} title="开始新面试" aria-label="开始新面试"><RotateCcw size={18} /></button>
      </header>
      <main>{children}</main>
    </div>
  );
}
