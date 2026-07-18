# InterviewHelper MVP

面向求职者的 AI 模拟面试训练工具。用户输入岗位描述（JD），系统生成面试题，逐题录制回答，并从回答内容、语音表达和可观察的视频行为中给出带证据的训练建议。

## MVP 范围

MVP 只实现一条完整链路：

1. 输入 JD。
2. 生成 5 道结构化问题。
3. 用户逐题录制音视频回答。
4. 系统分析回答内容、语速、停顿、填充词和有限的视频质量/行为指标。
5. 输出逐题反馈和整场总结。

不在 MVP 范围：实时数字人、实时打断、简历解析、模型微调、招聘筛选、心理状态或疾病诊断。

## 四人分工

| 负责人 | 工作目录 | 计划文档 | 核心职责 |
| --- | --- | --- | --- |
| 1：Web | `apps/web/` | [`docs/teams/01-web/PLAN.md`](docs/teams/01-web/PLAN.md) | JD、录制流程、进度与报告 UI |
| 2：Core API | `services/api/` | [`docs/teams/02-api/PLAN.md`](docs/teams/02-api/PLAN.md) | 公共 API、数据库、文件、状态与编排 |
| 3：Interviewer AI | `services/interviewer/` | [`docs/teams/03-interviewer-ai/PLAN.md`](docs/teams/03-interviewer-ai/PLAN.md) | 问题生成、回答内容评分与 Prompt |
| 4：Multimodal | `workers/multimodal/` | [`docs/teams/04-multimodal/PLAN.md`](docs/teams/04-multimodal/PLAN.md) | 音视频特征、时间证据和表达建议 |

## 开始开发前必读

1. [`docs/architecture.md`](docs/architecture.md)：整体架构和模块边界。
2. [`docs/contracts/API_CONTRACT.md`](docs/contracts/API_CONTRACT.md)：唯一接口真相源。
3. [`docs/contracts/STATE_AND_ERRORS.md`](docs/contracts/STATE_AND_ERRORS.md)：状态机和错误约定。
4. [`docs/integration/INTEGRATION.md`](docs/integration/INTEGRATION.md)：联调顺序和验收方法。
5. [`docs/plans/2026-07-17-mvp-implementation.md`](docs/plans/2026-07-17-mvp-implementation.md)：总体实施计划。

## 强制协作规则

- Web 只能调用 Core API，不能直接调用模型服务。
- Core API 是数据库、ID、状态和原始文件地址的唯一所有者。
- AI 两个模块不直接写业务数据库，只返回符合共享契约的 JSON。
- 接口字段变更必须先改 `docs/contracts/`，由调用方和提供方共同审查。
- 所有日期使用 ISO 8601 UTC；所有 ID 使用 UUID 字符串。
- 所有评分使用 `0.0` 到 `1.0`，无法可靠评分时返回 `null` 和原因，禁止编造。
- 产品输出是训练建议，不输出“焦虑症”“不诚实”“人格”等诊断或判断。

## 推荐 Git 流程

初始化仓库后，每人从 `main` 建独立分支：

```text
feat/web-interview-flow
feat/api-session-orchestration
feat/ai-question-evaluation
feat/mm-audio-video-analysis
```

每天至少同步一次 `main`。PR 必须小而可运行；共享契约 PR 优先合并，随后各模块再实现。
