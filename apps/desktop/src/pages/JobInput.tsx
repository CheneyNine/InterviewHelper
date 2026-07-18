import { BriefcaseBusiness, Camera, Check, FileText, LockKeyhole, Mic, Sparkles } from "lucide-react";
import { useState } from "react";
import { createInterview } from "../lib/api";
import { useInterviewStore } from "../store/interviewStore";
import type { CreateInterviewInput } from "../types";
import "../styles/job-input.css";

const sampleInput: CreateInterviewInput = {
  job_title: "ByteIntern 电商算法实习生",
  job_description: "负责抖音电商直播流量分发，利用海量数据构建机器学习算法和在线服务，分析用户、创作者与商家特征，持续优化流量分发策略，并与产品、运营和工程团队协作。",
  job_requirements: "计算机、机器学习等相关专业硕士在读；机器学习基础和编码能力扎实；熟悉算法与数据结构；有推荐、搜索、广告或大模型项目经验优先。",
  interview_stage: "技术面",
  question_count: 5,
  locale: "zh-CN",
};

const initialInput: CreateInterviewInput = {
  job_title: "",
  job_description: "",
  job_requirements: "",
  interview_stage: "技术面",
  question_count: 5,
  locale: "zh-CN",
};

const stages = ["初试", "技术面", "业务面", "HR面", "终面"];

export function JobInput() {
  const permissionGranted = useInterviewStore((state) => state.permissionGranted);
  const setPermissionGranted = useInterviewStore((state) => state.setPermissionGranted);
  const startInterview = useInterviewStore((state) => state.startInterview);
  const [input, setInput] = useState<CreateInterviewInput>(initialInput);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateInput = <K extends keyof CreateInterviewInput>(key: K, value: CreateInterviewInput[K]) => {
    setInput((current) => ({ ...current, [key]: value }));
  };

  const requestPermissions = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setPermissionGranted(true);
    } catch {
      setError("未能获得摄像头和麦克风权限。你仍可填写岗位信息，录制前需要在系统设置中开启权限。");
    }
  };

  const submit = async () => {
    const normalized = {
      ...input,
      job_title: input.job_title.trim(),
      job_description: input.job_description.trim(),
      job_requirements: input.job_requirements.trim(),
      interview_stage: input.interview_stage.trim(),
    };
    if (!normalized.job_title) {
      setError("请填写岗位名称。");
      return;
    }
    if (normalized.job_description.length < 20) {
      setError("岗位描述至少需要 20 个字符。");
      return;
    }
    if (normalized.job_requirements.length < 10) {
      setError("任职要求至少需要 10 个字符。");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const result = await createInterview(normalized);
      startInterview(result.interview, result.job);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建面试失败，请稍后重试。");
      setSubmitting(false);
    }
  };

  return (
    <div className="job-page page-grid">
      <section className="job-editor">
        <div className="eyebrow"><Sparkles size={15} /> 新建模拟面试</div>
        <h1>把目标岗位带进来，<br />我们从真实问题开始。</h1>
        <p className="lede">补充岗位和面试环节，我们会生成带参考思路与评分标准的结构化问题。</p>

        <div className="field-block">
          <div className="field-header">
            <label htmlFor="job-title"><BriefcaseBusiness size={16} />岗位名称</label>
            <button className="text-button" onClick={() => setInput(sampleInput)}>填入示例</button>
          </div>
          <input className="text-input" id="job-title" value={input.job_title} onChange={(event) => updateInput("job_title", event.target.value)} placeholder="例如：电商算法实习生" maxLength={200} />
        </div>

        <div className="field-block">
          <div className="field-header"><label htmlFor="job-description"><FileText size={16} />岗位描述</label></div>
          <textarea className="textarea-compact" id="job-description" value={input.job_description} onChange={(event) => updateInput("job_description", event.target.value)} placeholder="粘贴工作内容、团队方向和业务场景…" maxLength={12000} />
          <div className="field-footer"><span>工作职责与业务背景</span><span>{input.job_description.length.toLocaleString()} / 12,000</span></div>
        </div>

        <div className="field-block">
          <div className="field-header"><label htmlFor="job-requirements"><Check size={16} />任职要求</label></div>
          <textarea className="textarea-compact" id="job-requirements" value={input.job_requirements} onChange={(event) => updateInput("job_requirements", event.target.value)} placeholder="粘贴学历、技能、项目经验等要求…" maxLength={12000} />
          <div className="field-footer"><span>技能、经验与加分项</span><span>{input.job_requirements.length.toLocaleString()} / 12,000</span></div>
        </div>

        <div className="input-options">
          <div className="stage-control">
            <span>面试环节</span>
            <div className="segmented-control">
              {stages.map((stage) => <button className={input.interview_stage === stage ? "selected" : ""} key={stage} onClick={() => updateInput("interview_stage", stage)}>{stage}</button>)}
            </div>
          </div>
          <label className="count-control">
            <span>题目数量</span>
            <input type="number" min={1} max={10} value={input.question_count} onChange={(event) => updateInput("question_count", Math.min(10, Math.max(1, Number(event.target.value) || 1)))} />
          </label>
        </div>

        {error && <div className="inline-error">{error}</div>}
        <button className="button button-primary button-large" onClick={submit} disabled={submitting}>
          {submitting ? <span className="spinner small" /> : <Sparkles size={18} />}
          {submitting ? "正在创建…" : `生成 ${input.question_count} 道面试问题`}
        </button>
      </section>

      <aside className="privacy-panel">
        <div className="privacy-heading"><LockKeyhole size={20} /><div><strong>录制前说明</strong><span>你的隐私，由你掌控</span></div></div>
        <p>回答时会使用摄像头和麦克风，帮助分析内容结构、语速与有限的可观察表达特征。</p>
        <div className="permission-list">
          <div><span className="permission-icon"><Camera size={18} /></span><div><strong>摄像头</strong><small>本地预览与回答录像</small></div>{permissionGranted && <Check size={17} />}</div>
          <div><span className="permission-icon"><Mic size={18} /></span><div><strong>麦克风</strong><small>转写与语速、停顿分析</small></div>{permissionGranted && <Check size={17} />}</div>
        </div>
        <ul className="privacy-notes">
          <li>录制完成后先在本地回放</li>
          <li>只有点击“确认上传”才会发送</li>
          <li>重录不会创建服务端回答</li>
        </ul>
        <button className={`button ${permissionGranted ? "button-success" : "button-secondary"}`} onClick={requestPermissions}>
          {permissionGranted ? <Check size={17} /> : <LockKeyhole size={17} />}
          {permissionGranted ? "权限已就绪" : "检查摄像头与麦克风"}
        </button>
        <p className="disclaimer-mini">所有结果仅用于训练建议，不构成心理、医学或招聘结论。</p>
      </aside>
    </div>
  );
}
