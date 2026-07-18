import { AppShell } from "./components/AppShell";
import { GeneratingQuestions } from "./pages/GeneratingQuestions";
import { InterviewPage } from "./pages/Interview";
import { InterviewReportPage } from "./pages/InterviewReport";
import { JobInput } from "./pages/JobInput";
import { QuestionAnalysisPage } from "./pages/QuestionAnalysis";
import { useInterviewStore } from "./store/interviewStore";

export default function App() {
  const phase = useInterviewStore((state) => state.phase);
  return (
    <AppShell>
      {phase === "welcome" && <JobInput />}
      {phase === "generating" && <GeneratingQuestions />}
      {(phase === "interview" || phase === "analysis") && <InterviewPage />}
      {phase === "report" && <InterviewReportPage />}
      {phase === "answer-detail" && <QuestionAnalysisPage />}
    </AppShell>
  );
}
