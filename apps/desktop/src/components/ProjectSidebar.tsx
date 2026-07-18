import { CheckCircle2, Clock3, LoaderCircle, MessageSquareText, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError, getInterview, getInterviewReport, listInterviews } from "../lib/api";
import { useInterviewStore } from "../store/interviewStore";
import type { InterviewProjectSummary } from "../types";
import "../styles/workspace.css";

const statusLabels: Record<InterviewProjectSummary["status"], string> = {
  GENERATING_QUESTIONS: "生成中",
  QUESTIONS_READY: "待开始",
  IN_PROGRESS: "进行中",
  ANALYZING: "分析中",
  COMPLETED: "已完成",
  FAILED: "需重试",
};

function ProjectStatusIcon({ status }: { status: InterviewProjectSummary["status"] }) {
  if (status === "COMPLETED") return <CheckCircle2 size={13} />;
  if (status === "GENERATING_QUESTIONS" || status === "ANALYZING") return <LoaderCircle className="spin-icon" size={13} />;
  return <Clock3 size={13} />;
}

export function ProjectSidebar() {
  const projects = useInterviewStore((state) => state.projects);
  const activeInterviewId = useInterviewStore((state) => state.interview?.id);
  const setProjects = useInterviewStore((state) => state.setProjects);
  const loadInterview = useInterviewStore((state) => state.loadInterview);
  const showReport = useInterviewStore((state) => state.showReport);
  const newProject = useInterviewStore((state) => state.newProject);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [syncError, setSyncError] = useState(false);

  useEffect(() => {
    listInterviews()
      .then((items) => {
        setProjects(items);
        setSyncError(false);
        if (activeInterviewId && !items.some((item) => item.id === activeInterviewId)) {
          newProject();
        }
      })
      .catch(() => setSyncError(true));
  }, [activeInterviewId, newProject, setProjects]);

  const openProject = async (project: InterviewProjectSummary) => {
    if (loadingId) return;
    setLoadingId(project.id);
    try {
      const result = await getInterview(project.id);
      loadInterview(result.interview, result.questions, result.answers);
      if (project.status === "COMPLETED" || result.interview.status === "COMPLETED") {
        const report = await getInterviewReport(project.id);
        showReport(report);
      }
    } catch (error) {
      setSyncError(true);
      if (error instanceof ApiError && error.code === "INTERVIEW_NOT_FOUND") {
        const items = await listInterviews().catch(() => []);
        setProjects(items);
        if (project.id === activeInterviewId) newProject();
      }
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <aside className="project-sidebar">
      <div className="project-sidebar-header">
        <div><MessageSquareText size={16} /><strong>面试项目</strong></div>
        <button className="sidebar-new-button" onClick={newProject} title="新建面试项目" aria-label="新建面试项目"><Plus size={17} /></button>
      </div>

      <button className="new-project-command" onClick={newProject}><Plus size={15} />新建模拟面试</button>

      <div className="project-list" aria-label="面试项目列表">
        {projects.length === 0 && <p className="project-empty">创建第一个项目后，它会保存在这里。</p>}
        {projects.map((project) => (
          <button className={`project-list-item ${project.id === activeInterviewId ? "active" : ""}`} key={project.id} onClick={() => openProject(project)}>
            <span className="project-item-title">{project.job_title}</span>
            <span className="project-item-meta">
              <i><ProjectStatusIcon status={project.status} />{statusLabels[project.status]}</i>
              <i>{Math.min(project.answered_count, project.question_count)}/{project.question_count} 题</i>
            </span>
            {loadingId === project.id && <LoaderCircle className="project-loading spin-icon" size={15} />}
          </button>
        ))}
      </div>

      <div className={`project-sync-state ${syncError ? "offline" : ""}`}><span />{syncError ? "后端未连接，显示本地项目" : "项目已同步"}</div>
    </aside>
  );
}
