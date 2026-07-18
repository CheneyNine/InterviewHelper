import { BrainCircuit, CircleDot } from "lucide-react";
import type { PropsWithChildren } from "react";
import { useInterviewStore } from "../store/interviewStore";
import { ProjectSidebar } from "./ProjectSidebar";

const phaseOrder = ["generating", "interview", "report"];
const labels = ["生成问题", "模拟面试", "训练报告"];

export function AppShell({ children }: PropsWithChildren) {
  const phase = useInterviewStore((state) => state.phase);
  const interview = useInterviewStore((state) => state.interview);
  const normalizedPhase = phase === "answer-detail" ? "report" : phase;
  const current = normalizedPhase === "welcome" ? -1 : phaseOrder.indexOf(normalizedPhase);

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
        <div className="topbar-project-name">{interview?.job_title || "个人训练工作区"}</div>
      </header>
      <div className="workspace-body">
        <ProjectSidebar />
        <main className="workspace-main">{children}</main>
      </div>
    </div>
  );
}
