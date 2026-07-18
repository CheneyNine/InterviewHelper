# 面试报告分析方案 v1

## 1. 输入样例结论

`interview-report-dff678cf-1650-4fdb-9eb6-bf1201d7c2f4.json` 是单题报告，顶层包含：

- `question`：题目文本。
- `analysis.transcript`：逐字转写、语言、时间片段和置信度。
- `analysis.delivery`：语速、停顿、填充词、镜头外比例和可观察表达证据。
- `analysis.video`：采样帧、人脸可见性、表情和视频限制。
- `analysis.observable_state`：证据不足时的状态和免责声明。
- `formatted_report`：面向 UI 的格式化版本。

当前样例必须保留以下限制：ASR 中存在疑似误识别（例如“水预测”“水序任务”），视频没有足够的可见神情证据，观察文本有截断，转写片段只覆盖约 4 秒而媒体时长约 52 秒。LLM 只能引用这些证据，不能自行补全或诊断情绪。

## 2. 单题分析

### 2.1 调用链

```text
Core API 读取 Question + JD + 参考答案/评分标准
  ↓
Core API 将 JSON report 映射为 MultimodalAnswerReport
  ↓
POST /internal/v1/content-evaluations
  ↓
Interviewer LLM 返回单题结构化分析
```

Core API 不应只把 `question` 和逐字稿传给模型。技术正确性必须使用生成题目时保存的 `reference_answer` 和 `evaluation_rubric`。

### 2.2 映射规则

```json
{
  "job_title": "从 Interview 读取",
  "job_description": "从 Interview 读取",
  "question": "Question 中保存的完整 GeneratedQuestion",
  "multimodal_report": {
    "answer_text": "analysis.transcript.text",
    "facial_behavior_description": "formatted_report.dimensions[visible_expression] 的 summary + observations",
    "body_language_description": "analysis.video.observations 或 unavailable_reasons",
    "voice_delivery_description": "formatted_report.dimensions[tone_and_voice] 的 summary + analysis.delivery.observations",
    "metrics": "合并 analysis.delivery.metrics、analysis.video 指标和 duration_ms",
    "observations": "将 delivery/video observations 转为带 code、时间段、confidence 的证据"
  },
  "locale": "zh-CN"
}
```

### 2.3 单题返回结构

现有 `AnswerEvaluation` 继续作为底层评分结果；Core API 在 `AnswerAnalysis` 中保存以下扩展字段：

```json
{
  "answer_id": "uuid",
  "question_id": "uuid",
  "transcript_quality": {
    "score": 0.0,
    "issues": ["存在疑似 ASR 误识别", "片段覆盖不完整"],
    "limitations": ["不要据此断言用户没有说出相关内容"]
  },
  "dimensions": {
    "visible_expression": {
      "score": null,
      "summary": "没有足够的人脸可见证据",
      "evidence": [],
      "suggestions": []
    },
    "content_and_fluency": {
      "score": 0.0,
      "summary": "回答涉及 Transformer 的核心概念，但存在若干事实和表达问题",
      "evidence": ["逐字稿中的原文片段"],
      "metrics": {"words_per_minute": 249.4, "pause_ratio": 0.15},
      "suggestions": []
    },
    "tone_and_voice": {
      "score": null,
      "summary": "没有足够的独立语气证据",
      "evidence": [],
      "suggestions": []
    },
    "answer_structure": {
      "score": 0.0,
      "summary": "覆盖定义、动机和结构，但缺少清晰的分层收束",
      "evidence": [],
      "suggestions": []
    }
  },
  "strengths": [],
  "priority_improvements": [],
  "overall_score": 0.0,
  "limitations": [],
  "disclaimer": "这是训练反馈，不是心理、医学或招聘结论。"
}
```

评分原则：内容质量 70%，表达表现 30%；无法判断的维度使用 `null`，不强行给分。神情、镜头、动作和声音只能描述可观察表现，不能推断焦虑、不自信、诚实或人格。

## 3. 多题整体分析

### 3.1 处理流程

```text
每道 AnswerAnalysis 完成
  ↓
Core API 按 question.order 排序并读取每题摘要、评分、证据、限制和关键指标
  ↓
确定性聚合：计算总分、维度均值、覆盖率和趋势
  ↓
LLM 生成跨题总结：优势、优先改进、重复问题、练习计划
  ↓
保存 InterviewReport，Public API 返回报告
```

单题分析可以并发调用；整体报告必须等待所有已提交题目完成。整体报告 LLM 不重新评判原始视频，而是综合单题结果和少量证据，避免分数漂移。

### 3.2 整体报告结构

```json
{
  "interview_id": "uuid",
  "question_count": 5,
  "completed_count": 5,
  "overall_score": 0.74,
  "content_score": 0.78,
  "delivery_score": 0.65,
  "dimension_trends": {
    "content_and_fluency": {"average": 0.72, "trend": "stable"},
    "answer_structure": {"average": 0.68, "trend": "improving"},
    "tone_and_voice": {"average": null, "trend": "insufficient_evidence"}
  },
  "strengths": ["能够说明个人行动", "技术方向与岗位相关"],
  "priority_improvements": ["先给结论再展开", "补充量化结果"],
  "question_analyses": [
    {"question_id": "uuid", "answer_id": "uuid", "analysis_url": "/api/v1/answers/uuid/analysis"}
  ],
  "practice_plan": ["用 STAR 或目标-方法-结果结构重答第 2 题"],
  "limitations": ["部分视频未提供足够人脸证据"],
  "disclaimer": "这些结果是训练建议，不是心理、医学或招聘结论。"
}
```

### 3.3 分数聚合

- 每题先使用题目自己的 `evaluation_rubric` 得到题目分数。
- 整体 `content_score` 为各题内容分数的等权或按题目权重加权平均，权重策略写入报告。
- `delivery_score` 对有证据的题目加权平均；全部缺失时返回 `null`，而不是 0。
- `overall_score = content_score * 0.7 + delivery_score * 0.3`；若 delivery 缺失，报告必须说明重算规则。
- LLM 只负责解释趋势和生成建议，不能覆盖确定性分数。

## 4. API 设计

保留现有：

```text
POST /internal/v1/content-evaluations   # 单题
GET  /api/v1/answers/{answer_id}/analysis
GET  /api/v1/interviews/{interview_id}/report
```

Core API 内部新增一个报告编排任务即可，不需要把原始视频发送给 Interviewer：

```text
POST /internal/v1/interview-reports:generate
```

该接口接收已完成的单题分析摘要和证据，返回整体报告草稿。任务必须幂等，且只允许 Core API 调用。

## 5. MVP 实施顺序

1. 先把该 JSON 解析为现有 `MultimodalAnswerReport`，跑通单题 `content-evaluations`。
2. 保存单题分析和证据限制，不覆盖原始转写。
3. 为多题完成状态增加 `InterviewReport` 聚合器。
4. 先用确定性分数聚合，再增加整体 LLM 总结。
5. 添加 ASR/视频证据质量检查和报告中的 `limitations`。
