import { AppShell } from "./components/AppShell";
import { AnswerAnalysisPage } from "./pages/AnswerAnalysis";
import { GeneratingQuestions } from "./pages/GeneratingQuestions";
import { InterviewPage } from "./pages/Interview";
import { InterviewReportPage } from "./pages/InterviewReport";
import { JobInput } from "./pages/JobInput";
import { useInterviewStore } from "./store/interviewStore";

export default function App() {
  const phase = useInterviewStore((state) => state.phase);
  return (
    <AppShell>
      {phase === "welcome" && <JobInput />}
      {phase === "generating" && <GeneratingQuestions />}
      {phase === "interview" && <InterviewPage />}
      {phase === "analysis" && <AnswerAnalysisPage />}
      {phase === "report" && <InterviewReportPage />}
    </AppShell>
  );
}
